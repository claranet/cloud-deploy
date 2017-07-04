from mock import mock, MagicMock

from tests.helpers import get_aws_data
from web_ui.forms import get_aws_ami_ids


@mock.patch('web_ui.forms.cloud_connections')
@mock.patch('web_ui.forms.config', new={"display_amis_from_aws_accounts": None})
def test_get_aws_ami_ids(cloud_connections):
    connection_mock = MagicMock()
    connection_pool = MagicMock()
    cloud_connections.get.return_value.return_value = connection_pool
    connection_pool.get_connection.return_value = connection_mock

    connection_mock.get_all_images.return_value = get_aws_data('ec2--boto2--get-all-images', as_object=True)

    ret = get_aws_ami_ids('provider', 'region')

    connection_mock.get_all_images.assert_called_once()

    assert ret == [
        ("ami-abcedf", "123456789/ami-abcedf (ami.test.1)"),
        ("ami-ghijkl", "123456789/ami-ghijkl (None)"),
    ]
