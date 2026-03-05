from fastapi import status

from exceptions.service_exceptions import BaseServiceException


class SLMInferenceTimeoutException(BaseServiceException):
    """SLM local inference exceeded the configured time budget."""

    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    name = "SLM_INFERENCE_TIMEOUT"
    message = "SLM inference timeout exceeded."
