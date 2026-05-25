from utilities.choices import ChoiceSet


class ObjectLabelTypeChoices(ChoiceSet):
    ENVIRONMENT = "environment"
    APPLICATION = "application"
    SERVICE_CATEGORY = "servicecategory"
    SERVICE_ROLE = "servicerole"
    OTHER = "other"

    CHOICES = [
        (ENVIRONMENT, "Environment", "blue"),
        (APPLICATION, "Application", "green"),
        (SERVICE_CATEGORY, "ServiceCategory", "orange"),
        (SERVICE_ROLE, "ServiceRole", "purple"),
        (OTHER, "Other", "gray"),
    ]
