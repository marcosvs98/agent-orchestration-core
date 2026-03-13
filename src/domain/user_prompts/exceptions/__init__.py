from exceptions.service_exceptions import NotFoundServiceException


class UserPromptNotFoundException(NotFoundServiceException):
    message = "user_prompt_not_found"
