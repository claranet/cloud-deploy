from botocore.exceptions import ClientError
from mock import MagicMock, call

from ghost_aws import purge_launch_configuration
from tests.helpers import get_aws_data_paginator, get_test_application


def test_purge_launch_configuration():
    cloud_connection = MagicMock()
    connection = MagicMock()
    cloud_connection.get_connection.return_value = connection

    connection.get_paginator.return_value = get_aws_data_paginator("autoscaling--describe-launch-configurations")

    def delete_lc(LaunchConfigurationName=None):
        if LaunchConfigurationName == "launchconfig.test.eu-west-1.webfront.test-app.test3":
            raise ClientError({'Error': {'Code': 'ResourceInUse'}}, "message")

    connection.delete_launch_configuration.side_effect = delete_lc

    ret = purge_launch_configuration(cloud_connection, get_test_application(), 1)

    assert ret

    assert connection.delete_launch_configuration.call_count == 4
    connection.delete_launch_configuration.assert_has_calls([
        call(LaunchConfigurationName="launchconfig.test.eu-west-1.webfront.test-app.test1"),
        call(LaunchConfigurationName="launchconfig.test.eu-west-1.webfront.test-app.test3"),
        call(LaunchConfigurationName="launchconfig.test.eu-west-1.webfront.test-app.test4"),
        call(LaunchConfigurationName="launchconfig.test.eu-west-1.webfront.test-app.test5"),
    ], any_order=True)
