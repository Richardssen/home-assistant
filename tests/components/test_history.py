"""
tests.test_component_history
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the history component.
"""
# pylint: disable=protected-access,too-many-public-methods
import time
import os
import unittest
from unittest.mock import patch
from datetime import timedelta

import homeassistant.core as ha
import homeassistant.util.dt as dt_util
from homeassistant.components import history, recorder

from tests.common import (
    mock_http_component, mock_state_change_event, get_test_home_assistant)


class TestComponentHistory(unittest.TestCase):
    """ Tests homeassistant.components.history module. """

    def setUp(self):  # pylint: disable=invalid-name
        """ Init needed objects. """
        self.hass = get_test_home_assistant(1)
        self.init_rec = False

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

        if self.init_rec:
            recorder._INSTANCE.block_till_done()
            os.remove(self.hass.config.path(recorder.DB_FILE))

    def init_recorder(self):
        recorder.setup(self.hass, {})
        self.hass.start()
        recorder._INSTANCE.block_till_done()
        self.init_rec = True

    def test_setup(self):
        """ Test setup method of history. """
        mock_http_component(self.hass)
        self.assertTrue(history.setup(self.hass, {}))

    def test_last_5_states(self):
        """ Test retrieving the last 5 states. """
        self.init_recorder()
        states = []

        entity_id = 'test.last_5_states'

        for i in range(7):
            self.hass.states.set(entity_id, f"State {i}")

            if i > 1:
                states.append(self.hass.states.get(entity_id))

            self.hass.pool.block_till_done()
            recorder._INSTANCE.block_till_done()

        self.assertEqual(
            list(reversed(states)), history.last_5_states(entity_id))

    def test_get_states(self):
        """ Test getting states at a specific point in time. """
        self.init_recorder()
        states = []

        for i in range(5):
            state = ha.State(
                f'test.point_in_time_{i % 5}', f"State {i}", {'attribute_test': i}
            )


            mock_state_change_event(self.hass, state)
            self.hass.pool.block_till_done()

            states.append(state)

        recorder._INSTANCE.block_till_done()

        point = dt_util.utcnow() + timedelta(seconds=1)

        with patch('homeassistant.util.dt.utcnow', return_value=point):
            for i in range(5):
                state = ha.State(
                    f'test.point_in_time_{i % 5}',
                    f"State {i}",
                    {'attribute_test': i},
                )


                mock_state_change_event(self.hass, state)
                self.hass.pool.block_till_done()

        # Get states returns everything before POINT
        self.assertEqual(states,
                         sorted(history.get_states(point),
                                key=lambda state: state.entity_id))

        # Test get_state here because we have a DB setup
        self.assertEqual(
            states[0], history.get_state(point, states[0].entity_id))

    def test_state_changes_during_period(self):
        self.init_recorder()
        entity_id = 'media_player.test'

        def set_state(state):
            self.hass.states.set(entity_id, state)
            self.hass.pool.block_till_done()
            recorder._INSTANCE.block_till_done()

            return self.hass.states.get(entity_id)

        set_state('idle')
        set_state('YouTube')

        start = dt_util.utcnow()
        point = start + timedelta(seconds=1)
        end = point + timedelta(seconds=1)

        with patch('homeassistant.util.dt.utcnow', return_value=point):
            states = [
                set_state('idle'),
                set_state('Netflix'),
                set_state('Plex'),
                set_state('YouTube'),
            ]

        with patch('homeassistant.util.dt.utcnow', return_value=end):
            set_state('Netflix')
            set_state('Plex')

        self.assertEqual(
            {entity_id: states},
            history.state_changes_during_period(start, end, entity_id))
