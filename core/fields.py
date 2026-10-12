from rest_framework import serializers


class StrictIntegerField(serializers.IntegerField):
    """A JSON boolean, fraction or numeric string is not an integer."""

    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)
