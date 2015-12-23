cfnlambda
=========

cfnlambda is a collection of AWS Lambda tools to enable use of AWS Lambda 
functions with CloudFormation. At it's core it is the `cfn_response` function 
and the `handler_decorator` decorator. These enable an AWS Lambda function, 
launched from a CloudFormation stack, to log to CloudWatch, return data to the
CloudFormation stack and gracefully deal with exceptions.

Quickstart
----------
The easiest way to use cfnlambda is to use the `handler_decorator` decorator on
your AWS Lambda function.

::

    from cfnlambda import handler_decorator

    @handler_decorator()
    def lambda_handler(event, context):
        result = (float(event['ResourceProperties']['key1']) + 
                  float(event['ResourceProperties']['key2']))
        return {'sum': result}

handler_decorator
-----------------

When you decorate your AWS Lambda function with the `handler_decorator` a few
things happen. Your AWS Lambda function can now emit output back to the
CloudFormation stack that launched it simply by `returning`_ a dictionary of
key/value pairs, all of which become available to the CloudFormation stack as
attributes of the custom resource in the stack. These values can then be
accessed with the `Fn::GetAtt` CloudFormation function.

::

    { "Fn::GetAtt": [ "MyCustomResource", "a_key_returned_by_my_lambda_function" ] }

Any non-dictionary returned will be put into an custom resource attribute
called `result`. Any exceptions raised by your AWS Lambda function will be
caught by `handler_decorator`, logged to the CloudWatch logs and returned to
your CloudFormation stack in the `result` attribute.

::

    { "Fn::GetAtt": [ "MyCustomResource", "result" ] }

Unless the `delete_logs` argument is set to False in `handler_decorator`, all
CloudWatch logs generated while the stack was created, updated and deleted will
be deleted upon a successful stack deletion. If an exception is thrown during
stack deletion, the logs will always be retained to facilitate troubleshooting.
To force retention of logs after a stack is deleted, set `delete_logs` to False.

::

    from cfnlambda import handler_decorator
    logging.getLogger().setLevel(logging.DEBUG)

    @handler_decorator(delete_logs=False)
    def lambda_handler(event, context):
        mirror_text = event['ResourceProperties']['key1'][::-1]
        return {'MirrorText': mirror_text}


Finally, AWS Lambda functions decorated with `handler_decorator` will not
report a status of FAILED when a stack DELETE is attempted. This will prevent
a CloudFormation stack from getting stuck in a DELETE_FAILED state. One side
effect of this is that if your AWS Lambda function throws an exception while
trying to process a stack deletion, though the stack will show a status of
DELETE_COMPLETE, there could still be resources which your AWS Lambda function
created which have not been deleted. To disable this feature, pass
`hide_stack_delete_failure=False` as an argument to `handler_decorator`. 

::

    from cfnlambda import handler_decorator

    @handler_decorator(hide_stack_delete_failure=False)
    def lambda_handler(event, context):
        raise Exception(
            'This will result in a CloudFormation stack stuck in a
            DELETE_FAILED state')

handler_decorator usage walkthrough
###################################

Here is an example showing the creation of a very simple AWS Lambda function
which sums two values passed in from the CloudFormation stack ('key1' and 
'key2) and returns the result back to the stack as 'sum'.

Example assumptions:

* You have a pre-existing s3 bucket called `example-bucket-us-west-2` in the
  `us-west-2` region which is either public or readable by the user launching
  the CloudFormation stack.
* You have some way to upload a file into that s3 bucket. In the example we're
  using the `AWS CLI`_ tool. Here's how to `install and configure AWS CLI`_.

First, this Lambda code must be zipped and uploaded to an s3 bucket.

::

    from cfnlambda import handler_decorator
    import logging
    logging.getLogger().setLevel(logging.INFO)

    @handler_decorator()
    def lambda_handler(event, context):
        result = (float(event['ResourceProperties']['key1']) + 
                  float(event['ResourceProperties']['key2']))
        return {'sum': result}

Here are a set of commands to create and upload the AWS Lambda function

::

    dir=/path/to/PythonExampleDir
    mkdir $dir

    # Create your AWS Lambda function
    cat > $dir/example_lambda_module.py <<End-of-message
    from cfnlambda import handler_decorator
    import logging
    logging.getLogger().setLevel(logging.INFO)

    @handler_decorator()
    def lambda_handler(event, context):
        result = (float(event['ResourceProperties']['key1']) + 
                  float(event['ResourceProperties']['key2']))
        return {'sum': result}
    End-of-message

    pip install cfnlambda --no-deps -t $dir
    zip --junk-paths $dir/example_lambda_package.zip $dir/*
    aws --region us-west-2 s3 cp $dir/example_lambda_package.zip s3://example-bucket-us-west-2/

Next, the CloudFormation template must be written. Here is an simple example
CloudFormation stack that uses the Lambda function above. To use this example,
save this template to a file called `example_cloudformation_template.json`

::

    {
      "Resources" : {
        "SumInfo": {
          "Type": "Custom::SumInfo",
          "Properties": {
            "ServiceToken": { "Fn::GetAtt" : ["ExecuteSum", "Arn"] },
            "key1": "1.2",
            "key2": "5.9"
          }
        },
        "ExecuteSum": {
          "Type": "AWS::Lambda::Function",
          "Properties": {
            "Handler": "example_lambda_module.lambda_handler",
            "Role": { "Fn::GetAtt" : ["LambdaExecutionRole", "Arn"] },
            "Code": {
              "S3Bucket": "example-bucket-us-west-2",
              "S3Key": "example_lambda_package.zip"
            },        
            "Runtime": "python2.7"
          }
        },
        "LambdaExecutionRole": {
          "Type": "AWS::IAM::Role",
          "Properties": {
            "AssumeRolePolicyDocument": {
              "Version": "2012-10-17",
              "Statement": [{
                  "Effect": "Allow",
                  "Principal": {"Service": ["lambda.amazonaws.com"]},
                  "Action": ["sts:AssumeRole"]
              }]
            },
            "Policies": [{
              "PolicyName": "root",
              "PolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                  {
                    "Effect": "Allow",
                    "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": "arn:aws:logs:*:*:*"
                  },
                  {
                    "Effect": "Allow",
                    "Action": ["logs:DeleteLogGroup"],
                    "Resource": {"Fn::Join":["", ["arn:aws:logs:", {"Ref":"AWS::Region"},":",{"Ref":"AWS::AccountId"}, ":log-group:/aws/lambda/*"]]}
                  }
                ]
              }
            }]
          }
        }
      },
      "Outputs" : {
        "Sum" : {
          "Description" : "The sum of the two values",
          "Value" : { "Fn::GetAtt": [ "SumInfo", "sum" ] }
        }
      }
    }

Next, the CloudFormation template must be uploaded to execute the AWS
Lambda function.

::

    aws --region us-west-2 cloudformation create-stack --capabilities CAPABILITY_IAM --stack-name ExampleCloudFormationStack --template-body file:///home/user/example_cloudformation_template.json

Finally, you can see that the CloudFormation stack was created and the Lambda
function executed by looking at the CloudWatch logs that it created or at the
CloudFormation stack output. You should see in the stack output the "sum" of
the "key1" and "key2"

::

    aws --region us-west-2 cloudformation describe-stacks --stack-name ExampleCloudFormationStack

cfn_response
------------

`cfn_response` is a Python function designed as a drop in replacement for the
Node.js `cfn-response`_ function provided by AWS. It accepts the same arguments
and does the same thing.

`cfn_response` allows your AWS Lambda function to communicate out to the
CloudFormation stack that launched it. This communication is done through an
AWS signed URL. Here's an example of `cfn_response` in use

::

    from cfnlambda import cfn_response, Status, RequestType

    def lambda_handler(event, context):
        client = boto3.client('ec2')
        if event['RequestType'] == RequestType.DELETE:
            client.delete_key_pair(KeyName='example-cfnlambda-keypair')
            result = {'result': 'Key deleted'}
        else:
            keypair = client.create_key_pair(KeyName='example-cfnlambda-keypair')
            result = {'result': 'Key created',
                      'KeyMaterial': keypair['KeyMaterial']}
        cfn_response(event,
                     context,
                     Status.SUCCESS,
                     result)

This example would send the KeyMaterial (SSH private key) back to the
CloudFormation stack where it could be accessed like this

::

    { "Fn::GetAtt": [ "MyCustomResource", "KeyMaterial" ] }

How to contribute
-----------------
Feel free to open issues or fork and submit PRs.

* Issue Tracker: https://github.com/gene1wood/cfnlambda/issues
* Source Code: https://github.com/gene1wood/cfnlambda

Verifying the PyPI package
--------------------------
Verifying a PyPI package is a bit complicated, but doable. Verification can be
done through a chain of connected elements

1. The `cfnlambda` package file found in the `downloads section on PyPI`_
2. The `cfnlambda` pgp signature also found in the `downloads section on PyPI`_
3. The Key ID of the person who created the signature
4. A collection of accounts (github, twitter, etc) associated with the Key ID
   that illustrate that the person who signed the package is the author of the 
   package.

You can find the package files and signatures for `cfnlambda` in the
`downloads section on PyPI`_. Download the package file you want to verify and
the signature at the `pgp` link next to the package file.

Verify that the signature is a good signature by running

::

    gpg --keyid-format long --verify cfnlambda-1.0.0.tar.gz.asc

You should get a result like this

::

    gpg: Signature made Fri 22 May 2015 01:50:14 PM PDT
    gpg:                using DSA key 0123456789ABCDEF
    gpg: Can't check signature: public key not found

Now you know that the signature and the tar.gz match. Next you'll need to
verify that the person who created the signature is who you would expect. To do
this look at the `key ID` at the end of the second line (`0123456789ABCDEF` in 
this example). That is the ID of the signatory and should be the ID of the gpg 
key of the author of `cfnlambda`. Go to `keybase`_ and type the `key ID` into
the search bar. You should get back a single user's profile which lists out a
collection of accounts that the user has proved control of. A strong indicator
that the person is the author is if you can find `cfnlambda` in their github
account.

FAQ
---

Q: What causes the error `inner_decorator() takes exactly 1 argument (2 given): TypeError Traceback
(most recent call last): File "/var/runtime/awslambda/bootstrap.py", line
177, in handle_event_request result = request_handler(json_input, context)
TypeError: inner_decorator() takes exactly 1 argument (2 given)`

A: You likely used `@handler_decorator` to decorate your function instead of
`@handler_decorator()`. Because `handler_decorator` accepts arguments, you need
to use it with parenthesis. 

.. _AWS CLI: http://docs.aws.amazon.com/cli/latest/reference/s3/index.html
.. _install and configure AWS CLI: http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-set-up.html
.. _returning: https://docs.python.org/2/reference/simple_stmts.html#return
.. _cfn-response: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-lambda-function-code.html#cfn-lambda-function-code-cfnresponsemodule
.. _downloads section on PyPI: https://pypi.python.org/pypi/cfnlambda#downloads
.. _keybase: https://keybase.io/