import mock

from commands import preparebluegreen, swapbluegreen, purgebluegreen
from commands import createinstance
from commands import updateautoscaling

from tests.helpers import get_test_application


@mock.patch('commands.preparebluegreen.ghost_has_blue_green_enabled')
def test_command_prepare_bg_available(ghost_has_blue_green_enabled):
    ghost_has_blue_green_enabled.return_value = True
    app = get_test_application(name="test-app", _id='id')
    ret = preparebluegreen.is_available(None)
    assert ret == True

    ret = preparebluegreen.is_available(app)
    assert ret == False

    app['blue_green'] = {'color': 'blue'}
    ret = preparebluegreen.is_available(app)
    assert ret == True

    ghost_has_blue_green_enabled.return_value = False
    ret = preparebluegreen.is_available(None)
    assert ret == False


@mock.patch('commands.swapbluegreen.ghost_has_blue_green_enabled')
def test_command_swap_bg_available(ghost_has_blue_green_enabled):
    ghost_has_blue_green_enabled.return_value = True
    app = get_test_application(name="test-app", _id='id')
    ret = swapbluegreen.is_available(None)
    assert ret == True

    ret = swapbluegreen.is_available(app)
    assert ret == False

    app['blue_green'] = {'color': 'blue'}
    ret = swapbluegreen.is_available(app)
    assert ret == True

    ghost_has_blue_green_enabled.return_value = False
    ret = swapbluegreen.is_available(None)
    assert ret == False


@mock.patch('commands.purgebluegreen.ghost_has_blue_green_enabled')
def test_command_purge_bg_available(ghost_has_blue_green_enabled):
    ghost_has_blue_green_enabled.return_value = True
    app = get_test_application(name="test-app", _id='id')
    ret = purgebluegreen.is_available(None)
    assert ret == True

    ret = purgebluegreen.is_available(app)
    assert ret == False

    app['blue_green'] = {'color': 'blue'}
    ret = purgebluegreen.is_available(app)
    assert ret == True

    ghost_has_blue_green_enabled.return_value = False
    ret = purgebluegreen.is_available(None)
    assert ret == False


def test_command_createinstance_available():
    app = get_test_application(name="test-app", _id='id')
    ret = createinstance.is_available(app)
    assert ret == True

    del app['ami']
    ret = createinstance.is_available(app)
    assert ret == False


def test_command_updateautoscaling_available():
    app = get_test_application(name="test-app", _id='id')
    ret = updateautoscaling.is_available(app)
    assert ret == True

    app['autoscale']['name'] = ''
    ret = updateautoscaling.is_available(app)
    assert ret == False

    del app['autoscale']
    ret = updateautoscaling.is_available(app)
    assert ret == False
