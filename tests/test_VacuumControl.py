import mock
import pytest
from datetime import datetime, timedelta, time
from VacuumControl import VacuumControl, VacuumControlConfiguration
import logging
from unittest.mock import ANY
from freezegun import freeze_time
import uuid
import re

class TestVacuumControl:

    @pytest.fixture
    @freeze_time("2019-10-16 00:02:02", tz_offset=2)
    def vacuumcontrol(self, given_that):
        vacuumcontrol = VacuumControl(
            None, VacuumControl.__name__, None, None, None, None, None)
        vacuumcontrolconfig = VacuumControlConfiguration(
            None, VacuumControlConfiguration.__name__, None, None, None, None, None)

        # Set initial state
        vacuumlist = ['robot1', 'robot2', 'robot3', 'robot4']
        for vacuum in vacuumlist:
            given_that.state_of(f"vacuum.{vacuum}").is_set_to(
                "docked", {'friendly_name': f"{vacuum}", 'battery_level': 100, 'battery_icon': 'mdi:battery-charging-100', 'fan_speed': 'Medium', 'status': 'Charging', 'supported_features': 14204, 'fan_speed_list': 'Silent, Standard, Medium, Turbo, Gentle, Auto'})
            for varbool in vacuumcontrolconfig.variables_boolean:
                print(f"input_boolean.control_vacuum_{vacuum}_{varbool}")
                given_that.state_of(
                    f"input_boolean.control_vacuum_{vacuum}_{varbool}").is_set_to("on")

            for vardate in vacuumcontrolconfig.variables_datetime:
                print(f"input_datetime.control_vacuum_{vacuum}_{vardate}")
                given_that.state_of(
                    f"input_datetime.control_vacuum_{vacuum}_{vardate}").is_set_to("07:30:00", {"hour": 7, "minute": 30, "second": 0})

        for varboolglob in vacuumcontrolconfig.variables_boolean_global:
            print(f"input_boolean.control_vacuum_{varboolglob}")
            given_that.state_of(
                f"input_boolean.control_vacuum_{varboolglob}").is_set_to("on")

        # set namespace
        vacuumcontrol.set_namespace(None)

        # passed args
        given_that.passed_arg('debug').is_set_to('True')

        vacuumcontrol.initialize()
        given_that.mock_functions_are_cleared()
        return vacuumcontrol

    # Test if alle handles are created and all config variables are watched
    @freeze_time("2019-10-16 12:32:02", tz_offset=2)
    def test_initialize(self, given_that, vacuumcontrol, assert_that, caplog, time_travel):
        #caplog.set_level(logging.DEBUG)
        
        vacuumcontrolconfig = VacuumControlConfiguration(
            None, VacuumControlConfiguration.__name__, None, None, None, None, None)

        #get list of vacuum entities
        vacuumlist = list()
        statedict = vacuumcontrol.get_state()
        for entity in statedict:
            if re.match('^vacuum.*', entity, re.IGNORECASE):
                vacuumlist.append(vacuumcontrol._getid(statedict, entity))
        vacuumcontrol.initialize()

        # Watch alle config variables for changes
        for vacuum in vacuumlist:
            for varbool in vacuumcontrolconfig.variables_boolean:
                assert_that(vacuumcontrol).listens_to.state(f"input_boolean.control_vacuum_{vacuum}_{varbool}", entityid=f"{vacuum}", duration=10) \
                .with_callback(vacuumcontrol._config_change)

            for vardate in vacuumcontrolconfig.variables_datetime:
                assert_that(vacuumcontrol).listens_to.state(f"input_datetime.control_vacuum_{vacuum}_{vardate}", entityid=f"{vacuum}",duration=10) \
                .with_callback(vacuumcontrol._config_change)

        for varboolglob in vacuumcontrolconfig.variables_boolean_global:
            assert_that(vacuumcontrol).listens_to.state(f"input_boolean.control_vacuum_{varboolglob}", duration=10) \
                .with_callback(vacuumcontrol._config_change_global)

        #check if handles are created
        for vacuum in vacuumlist:
            assert_that(vacuumcontrol).registered.run_at(datetime.now() + timedelta(seconds=5), entityid=f"{vacuum}").with_callback(vacuumcontrol._control_vacuum)
        
    # Cancel all handles
    # control_blinds_enable_global is off
    @freeze_time("2019-10-16 12:32:02", tz_offset=2)
    def test_config_change_control_vacuum_enable_global_off(self, given_that, vacuumcontrol, assert_that, caplog, time_travel):

        #get list of vacuum entities
        vacuumlist = list()
        statedict = vacuumcontrol.get_state()
        for entity in statedict:
            if re.match('^vacuum.*', entity, re.IGNORECASE):
                vacuumlist.append(vacuumcontrol._getid(statedict, entity))

        given_that.state_of(
            f'input_boolean.control_vacuum_enable_global').is_set_to("off")
        
        handlelist = list()
        for vacuum in vacuumlist:
            handlelist.append(vacuumcontrol._get_handle(vacuum, 'vc_handle'))
        
        vacuumcontrol.cancel_timer = mock.MagicMock()
        vacuumcontrol._config_change_global('input_boolean.control_vacuum_enable_global', 'state', 'on', 'off', {})
        
        #now we check if all "old" handles have been canceled
        for handle in handlelist:
            vacuumcontrol.cancel_timer.called_with(handle)
            
    # control vacuum
    # start einplanen
    @freeze_time("2019-10-16 05:00:02", tz_offset=2)
    def test_control_vacuum(self, given_that, vacuumcontrol, assert_that, caplog, time_travel):        
    
        #get list of vacuum entities
        vacuumlist = list()
        statedict = vacuumcontrol.get_state()
        for entity in statedict:
            if re.match('^vacuum.*', entity, re.IGNORECASE):
                vacuumlist.append(vacuumcontrol._getid(statedict, entity))

        vc_start_time = datetime.now().replace(
                        hour=7, minute=30, second=0,
                        microsecond=0)
        
        for vacuum in vacuumlist:
            vacuumcontrol._control_vacuum({"entityid":vacuum})
            assert_that(vacuumcontrol).registered.run_at(vc_start_time, entityid=f"{vacuum}").with_callback(vacuumcontrol._start_vacuum)

            
    # control vacuum
    # start time passed
    @freeze_time("2019-10-16 12:32:02", tz_offset=2)
    def test_control_vacuum_passed(self, given_that, vacuumcontrol, assert_that, caplog, time_travel):        
    
        #get list of vacuum entities
        vacuumlist = list()
        statedict = vacuumcontrol.get_state()
        for entity in statedict:
            if re.match('^vacuum.*', entity, re.IGNORECASE):
                vacuumlist.append(vacuumcontrol._getid(statedict, entity))
                
        for vacuum in vacuumlist:
            vacuumcontrol._control_vacuum({"entityid":vacuum})
            dtime = datetime.now().replace(
                        hour=0, minute=0, second=0,
                        microsecond=0) + timedelta(days=1, seconds=5)
            assert_that(vacuumcontrol).registered.run_at(dtime, entityid=f"{vacuum}").with_callback(vacuumcontrol._control_vacuum)
            

    #_start_vacuum
    @freeze_time("2019-10-16 12:32:02", tz_offset=2)
    def test_start_vacuum(self, given_that, vacuumcontrol, assert_that, caplog, time_travel):
    
        #get list of vacuum entities
        vacuumlist = list()
        statedict = vacuumcontrol.get_state()
        for entity in statedict:
            if re.match('^vacuum.*', entity, re.IGNORECASE):
                vacuumlist.append(vacuumcontrol._getid(statedict, entity))
                
                
        for vacuum in vacuumlist:
            vacuumcontrol._start_vacuum({"entityid":vacuum})
            assert_that('vacuum/start').was.called_with(entity_id=f"vacuum.{vacuum}")
            assert_that(vacuumcontrol).registered.run_at(datetime.now() + timedelta(minutes=5), entityid=f"{vacuum}").with_callback(vacuumcontrol._control_vacuum)
