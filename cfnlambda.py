"""Collection of tools to enable use of AWS Lambda with CloudFormation.

Classes:
    Status: CloudFormation custom resource status constants
    RequestType: CloudFormation custom resource request type constants
    PythonObjectEncoder: Custom JSON Encoder that allows encoding of
        un-serializable objects
Functions:
    cfn_response: Format and send a CloudFormation custom resource object.
    handler_decorator: Decorate an AWS Lambda function to add exception
        handling, emit CloudFormation responses and log.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""
import logging
import json
from functools import wraps
import boto3
from botocore.vendored import requests
import traceback
import httplib

logger = logging.getLogger(__name__)


class Status:
    """CloudFormation custom resource status constants

    http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/crpg-ref-responses.html
    """

    def __init__(self, value, reason=None):
        self.value = value
        self.reason = reason

    def __repr__(self):
        r = '{}'.format(self.value)
        if self.reason:
            r += '({})'.format(self.reason)
        return r

    def isSuccess(self):
        return self.value == 'SUCCESS' or (self.isFinished() and self.value.value == 'SUCCESS')

    def isFailed(self):
        return self.value == 'FAILED' or (self.isFinished() and self.value.value == 'FAILED')

    def isFinished(self):
        return isinstance(self.value, Status)

    @classmethod
    def getFailed(cls, reason):
        return cls('FAILED', reason)

    @classmethod
    def getFinished(cls, status):
        return cls(status)

Status.SUCCESS = Status('SUCCESS')
Status.FAILED = Status('FAILED')


class RequestType:
    """CloudFormation custom resource request type constants

    http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/crpg-ref-requesttypes.html
    """
    CREATE = 'Create'
    DELETE = 'Delete'
    UPDATE = 'Update'


class PythonObjectEncoder(json.JSONEncoder):
    """Custom JSON Encoder that allows encoding of un-serializable objects

    For object types which the json module cannot natively serialize, if the
    object type has a __repr__ method, serialize that string instead.

    Usage:
        >>> example_unserializable_object = {'example': set([1,2,3])}
        >>> print(json.dumps(example_unserializable_object,
                             cls=PythonObjectEncoder))
        {"example": "set([1, 2, 3])"}
    """
    def default(self, obj):
        if isinstance(obj,
                      (list, dict, str, unicode,
                       int, float, bool, type(None))):
            return json.JSONEncoder.default(self, obj)
        elif hasattr(obj, '__repr__'):
            return obj.__repr__()
        else:
            return json.JSONEncoder.default(self, obj.__repr__())


def cfn_response(event,
                 context,
                 response_status,
                 response_data={},
                 physical_resource_id=None):
    """Format and send a CloudFormation custom resource object.

    Creates a JSON payload with a CloudFormation custom resource object[1],
    then HTTP PUTs this payload to an AWS signed URL. Replicates the
    functionality of the NodeJS cfn-response module in python.[2]

    Args:
        event: A dictionary containing CloudFormation custom resource provider
            request fields.[3]
        context: An AWS LambdaContext object containing lambda runtime
            information.[4]
        response_status: A status of SUCCESS or FAILED to send back to
            CloudFormation.[2] Use the Status.SUCCESS and Status.FAILED
            constants, or Status.getFailed() to provide a reason for the
            failure. If the status was wrapped using Status.getFinished(),
            the call is a noop and returns None.
        response_data: A dictionary of key value pairs to pass back to
            CloudFormation which can be accessed with the Fn::GetAtt function
            on the CloudFormation custom resource.[5]
        physical_resource_id: An optional unique identifier of the custom
            resource that invoked the function. By default, the name of the
            CloudWatch Logs log stream is used.

    Returns:
        requests.Response object

    Raises:
        No exceptions raised

    [1]: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-function-code.html#cfn-lambda-function-code-cfnresponsemodule
    [2]: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/crpg-ref-responses.html
    [3]: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/crpg-ref-requests.html#crpg-ref-request-fields
    [4]: http://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
    [5]: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/crpg-ref-responses.html#crpg-ref-responses-data
    """
    if isinstance(response_status, Status) and response_status.isFinished():
        return

    if physical_resource_id is None:
        physical_resource_id = context.log_stream_name
    default_reason = ("See the details in CloudWatch Log Stream: %s" %
                   context.log_stream_name)
    body = {
        "Status": response_status.value if isinstance(response_status, Status) else response_status,
        "Reason": response_status.reason or default_reason if isinstance(response_status, Status) else default_reason,
        "PhysicalResourceId": physical_resource_id,
        "StackId": event['StackId'],
        "RequestId": event['RequestId'],
        "LogicalResourceId": event['LogicalResourceId'],
        "Data": response_data
    }
    response_body = json.dumps(body)
    logger.debug("Response body: %s", response_body)
    try:
        response = requests.put(event['ResponseURL'],
                                data=response_body)
        body_text = ""
        if response.status_code // 100 != 2:
            body_text = "\n" + response.text
        logger.debug("Status code: %s %s%s" % (response.status_code, httplib.responses[response.status_code], body_text))
            
        # logger.debug("Status message: %s" % response.status_message)
        # how do we get the status message?
        return response
    except Exception as e:
        logger.error("send(..) failed executing https.request(..): %s" %
                     e.message)
        logger.debug(traceback.format_exc())


def handler_decorator(delete_logs=True,
                      hide_stack_delete_failure=True):
    """Decorate an AWS Lambda function to add exception handling, emit
    CloudFormation responses and log.

    Usage:
        >>> @handler_decorator()
        ... def lambda_handler(event, context):
        ...     sum = (float(event['ResourceProperties']['key1']) +
        ...            float(event['ResourceProperties']['key2']))
        ...     return {'sum': sum}

    Args:
        delete_logs: A boolean which, when True, will cause a successful
            stack deletion to trigger the deletion of the CloudWatch logs that
            were generated. If delete_logs is False or if there is a problem
            during stack deletion, the logs are left in place.
        hide_stack_delete_failure: A boolean which, when True, will report
            SUCCESS to CloudFormation when a stack deletion is requested
            regardless of the success of the AWS Lambda function. This will
            prevent stacks from being stuck in DELETE_FAILED states but will
            potentially result in resources created by the AWS Lambda function
            to remain in existence after stack deletion. If
            hide_stack_delete_failure is False, an exception in the AWS Lambda
            function will result in DELETE_FAILED upon an attempt to delete
            the stack.

    Returns:
        A decorated function

    Raises:
        No exceptions
    """

    def inner_decorator(handler):
        """Bind handler_decorator to handler_wrapper in order to enable passing
        arguments into the handler_decorator decorator.

        Args:
            handler: The Lambda function to decorate

        Returns:
            A decorated function

        Raises:
            No exceptions
        """
        @wraps(handler)
        def handler_wrapper(event, context):
            """Executes an AWS Lambda function and emits a CloudFormation response.

            Executes an AWS Lambda function (handler), catches exceptions and
            logs them, then emits a CloudFormation custom resource response
            indicating the handler's success or failure along with any
            key/value pairs passed back.

            Upon successful stack DELETE by the wrapped function, delete the
            AWS Lambda CloudWatch log group created by the lambda function.

            Args:
                event: A dictionary containing CloudFormation custom resource
                    provider request fields.[1]
                context: An AWS LambdaContext object containing lambda runtime
                    information.[2]

            Returns:
                If the handler returns a Status object, the wrapper returns an
                empty dict.
                
                If the handler returns two values, the first being a Status object,
                the wrapper returns the second value.
                
                Otherwise, the wrapper returns the value returned by the handler.

            Returns to CloudFormation:
                TODO

            Raises:
                All exceptions are caught and logged but not raised

            [1]: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/crpg-ref-requests.html#crpg-ref-request-fields
            [2]: http://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html
            """
            logger.info('REQUEST RECEIVED: %s' % json.dumps(event))
            logger.info('LambdaContext: %s' %
                        json.dumps(vars(context), cls=PythonObjectEncoder))
            result = None
            try:
                result = handler(event, context)
                if isinstance(result, Status):
                    status = result
                    result = None
                elif isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], Status):
                    status, result = result
                else:
                    status = Status.SUCCESS if result else Status.FAILED
                if result is False:
                    message = "Function %s returned False." % handler.__name__
                    logger.error(message)
                    status = Status.FAILED
                    result = {'result': message}
            except Exception as e:
                status = Status.getFailed('Function %s failed due to exception "%s".' %
                           (handler.__name__, e.message))
                result = {}
                logger.error(status.reason)
                logger.debug(traceback.format_exc())

            if not result:
                result = {}

            if event['RequestType'] == RequestType.DELETE:
                if status == Status.FAILED and hide_stack_delete_failure:
                    message = (
                        'There may be resources created by the AWS '
                        'Lambda that have not been deleted and cleaned up '
                        'despite the fact that the stack status may be '
                        'DELETE_COMPLETE.')
                    logger.error(message)
                    result['result'] = result.get('result', '') + ' %s' % message
                    status = Status.SUCCESS

                if status.isSuccess() and delete_logs:
                    logging.disable(logging.CRITICAL)
                    logs_client = boto3.client('logs')
                    logs_client.delete_log_group(
                        logGroupName=context.log_group_name)
            result = (dict(result) if isinstance(result, dict) else {'result': result})
            if not status.isFinished():
                cfn_response(event,
                             context,
                             status,
                             result,
                             )
            return result
        return handler_wrapper
    return inner_decorator
