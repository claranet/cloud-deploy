import mock

from commands import preparebluegreen, swapbluegreen, purgebluegreen
from commands import createinstance
from commands import updateautoscaling

from tests.helpers import get_test_application


@mock.patch('commands.preparebluegreen.ghost_has_blue_green_enabled')
def test_command_prepare_bg_available(ghost_has_blue_green_enabled):
    app = get_test_application(name="test-app", _id='id')
    ret = preparebluegreen.is_available_for_current_application(None)
    assert ret == False

    ret = preparebluegreen.is_available_for_current_application(app)
    assert ret == False

    ghost_has_blue_green_enabled.return_value = True
    app['blue_green'] = {'color': 'blue'}
    ret = preparebluegreen.is_available_for_current_application(app)
    assert ret == True


@mock.patch('commands.swapbluegreen.ghost_has_blue_green_enabled')
def test_command_swap_bg_available(ghost_has_blue_green_enabled):
    app = get_test_application(name="test-app", _id='id')
    ret = swapbluegreen.is_available_for_current_application(None)
    assert ret == False

    ret = swapbluegreen.is_available_for_current_application(app)
    assert ret == False

    ghost_has_blue_green_enabled.return_value = True
    app['blue_green'] = {'color': 'blue'}
    ret = swapbluegreen.is_available_for_current_application(app)
    assert ret == True


@mock.patch('commands.purgebluegreen.ghost_has_blue_green_enabled')
def test_command_purge_bg_available(ghost_has_blue_green_enabled):
    app = get_test_application(name="test-app", _id='id')
    ret = purgebluegreen.is_available_for_current_application(None)
    assert ret == False

    ret = purgebluegreen.is_available_for_current_application(app)
    assert ret == False

    ghost_has_blue_green_enabled.return_value = True
    app['blue_green'] = {'color': 'blue'}
    ret = purgebluegreen.is_available_for_current_application(app)
    assert ret == True


def test_command_createinstance_available():
    app = get_test_application(name="test-app", _id='id')
    ret = createinstance.is_available_for_current_application(app)
    assert ret == True

    del app['ami']
    ret = createinstance.is_available_for_current_application(app)
    assert ret == False


def test_command_updateautoscaling_available():
    app = get_test_application(name="test-app", _id='id')
    ret = updateautoscaling.is_available_for_current_application(app)
    assert ret == True

    app['autoscale']['name'] = ''
    ret = updateautoscaling.is_available_for_current_application(app)
    assert ret == False

    del app['autoscale']
    ret = updateautoscaling.is_available_for_current_application(app)
    assert ret == False
