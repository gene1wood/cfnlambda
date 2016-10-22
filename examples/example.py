"""Example lambda function code for cfn."""
from cfnlambda import handler_decorator
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


@handler_decorator()
def lambda_handler(event, context):
    """lambda handler method entry point."""
    result = (float(event['ResourceProperties']['key1']) +
              float(event['ResourceProperties']['key2']))
    LOGGER.info("Here is an example log message")
    return {'sum': result}
