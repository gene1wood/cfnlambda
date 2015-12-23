from cfnlambda import handler_decorator
import logging

logger = logging.getLogger(__name__)
logging.getLogger().setLevel(logging.INFO)


@handler_decorator()
def lambda_handler(event, context):
    result = (float(event['ResourceProperties']['key1']) +
              float(event['ResourceProperties']['key2']))
    logger.info("Here is an example log message")
    return {'sum': result}
