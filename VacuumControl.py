import os
import re
import traceback
from datetime import datetime, timedelta
from threading import Semaphore
from helper.Helper import BaseClass


class VacuumControl(BaseClass):

    def initialize(self):
        self._version=1.0
        self._lock = Semaphore(1)
        # run over all covers an check if configurations are available
        # then start the spcific handlers for each covers
        statedict = self.get_state()
        self._vacuumdict = dict()
        changeduration = 10
        self._log_info(f"Runnging version: {self._version}")
        for entity in statedict:
            if re.match('^vacuum.*', entity, re.IGNORECASE):
                # detected vacuum
                id_ = self._getid(statedict, entity)
                handledict = dict()
                # create listeners for config changes
                for configvar in VacuumControlConfiguration.variables_boolean:
                    cvarname = "input_boolean.control_vacuum_%s_%s" % (
                        id_, configvar)
                    if self.entity_exists(cvarname):
                        self._log_debug(f"Listen for config change on: {cvarname}")
                        handle = self.listen_state(
                            self._config_change, cvarname, entityid=id_,
                            duration=changeduration)
                        handledict.update({cvarname: handle})
                for configvar in VacuumControlConfiguration.variables_number:
                    cvarname = "input_number.control_vacuum_%s_%s" % (
                        id_, configvar)
                    if self.entity_exists(cvarname):
                        self._log_debug(f"Listen for config change on: {cvarname}")
                        handle = self.listen_state(
                            self._config_change, cvarname, entityid=id_,
                            duration=changeduration)
                        handledict.update({cvarname: handle})
                for configvar in VacuumControlConfiguration.variables_datetime:
                    cvarname = "input_datetime.control_vacuum_%s_%s" % (
                        id_, configvar)
                    if self.entity_exists(cvarname):
                        self._log_debug(f"Listen for config change on: {cvarname}")
                        handle = self.listen_state(
                            self._config_change, cvarname, entityid=id_,
                            duration=changeduration)
                        handledict.update({cvarname: handle})

                # create variables per vacuum
                vardict = dict()
                vardict.update({"vacuumID": entity})

                # create vacuum control handle
                if len(handledict) > 0:
                    vc_handle = None
                    self._log_debug(
                        "input_boolean.control_vacuum_%s_automatic_control: %s"
                        % (id_, self.get_state(
                            "input_boolean.control_vacuum_%s_automatic_control"
                            % id_)), prefix=id_)
                    self._log_debug(
                        "input_boolean.control_vacuum_enable_global: %s" %
                        (self.get_state(
                            "input_boolean.control_vacuum_enable_global")),
                        prefix=id_)
                    if (self.get_state(
                            "input_boolean.control_vacuum_%s_automatic_control"
                            % id_) == "on" and self.get_state(
                            "input_boolean.control_vacuum_enable_global")
                            == "on"):
                        self._log_debug(f"Create handle entityid: {id_}")
                        vc_handle = self.run_at(
                            self._control_vacuum,
                            datetime.now() + timedelta(seconds=5), entityid=id_)
                    handledict.update({"vc_handle": vc_handle})

                    d = dict()
                    d.update({"handledict": handledict})
                    d.update({"vardict": vardict})
                    self._vacuumdict.update({id_: d})

        # add global config handlers
        handledict = dict()
        for configvar in VacuumControlConfiguration.variables_boolean_global:
            cvarname = "input_boolean.control_vacuum_%s" % configvar
            self._log_debug(f"cvarname: {cvarname}")
            if self.entity_exists(cvarname):
                self._log_debug(f"Listen for config change on: {cvarname}")
                handle = self.listen_state(
                    self._config_change_global, cvarname, duration=changeduration)
                handledict.update({cvarname: handle})
        d = dict()
        d.update({"handledict": handledict})
        self._vacuumdict.update({"global": d})

    def _get_handle(self, entityid, handle):
        edict = self._vacuumdict.get(entityid, dict())
        handledict = edict.get('handledict', dict())
        return handledict.get(handle, None)

    def _set_handle(self, entityid, varname, handle):
        edict = self._vacuumdict.get(entityid, dict())
        handledict = edict.get('handledict', dict())
        handledict.update({varname: handle})
        edict.update({"handledict": handledict})

    def _get_variable(self, entityid, varname):
        edict = self._vacuumdict.get(entityid, dict())
        vardict = edict.get('vardict', dict())
        self._log_debug("entityid: %s, varname: %s, len(edict):%s,\
                        len(vardict):%s" % (
            entityid, varname, len(edict), len(vardict)))
        self._log_debug(f"vardict: varname: {vardict.get(varname, None)}")
        return vardict.get(varname, None)

    def _set_variable(self, entityid, varname, value):
        edict = self._vacuumdict.get(entityid, dict())
        vardict = edict.get('vardict', dict())
        vardict.update({varname: value})
        edict.update({"vardict": vardict})

    def _cancel_restart_handle(self, entityid):
        #config has changed for a specific entity
        self._log_debug("cancel_restart_handle", prefix=entityid)
        # cancel and create new vacuum control handle
        vc_handle = self._get_handle(entityid, 'vc_handle')
        if vc_handle is not None:
            self._log_debug(f"Cancel handle for {entityid}")
            self.cancel_timer(vc_handle)
            vc_handle = None
        if (self.get_state(
            "input_boolean.control_vacuum_%s_automatic_control"
            % entityid) == "on" and self.get_state(
                "input_boolean.control_vacuum_enable_global") == "on"):
            vc_handle = self.run_at(
                self._control_vacuum,
                datetime.now() + timedelta(seconds=5), entityid=entityid)
        else:
            self._log_info(
                "Control vacuum global or per vacuum is disabled\
                (Enable per vacuum: %s, Enable Global: %s)" %
                (self.get_state(
                    "input_boolean.control_vacuum_%s_automatic_control"
                    % entityid), self.get_state(
                    "input_boolean.control_vacuum_enable_global")),
                prefix=entityid)
        self._set_handle(entityid, "vc_handle", vc_handle)

    def _get_vacuumlist(self):
        vacuumlist = list()
        for k in self._vacuumdict:
            self._log_debug(f"vacuumlist: {k}")
            if k != "global":
                vacuumlist.append(k)
        return vacuumlist

    def _config_change_global(self, entity, attribute, old, new, kwargs):
        #global variable changed
        require_reset = ["input_boolean.control_vacuum_enable_global"]
        if entity in require_reset:
            #disable all handles
            for vacuum in self._get_vacuumlist():
                self._log_debug("Reset required. Disable all handles")
                self._config_change(entity, None, old, new, {'entityid': vacuum})

    def _config_change(self, entity, attribute, old, new, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._log_debug(f"entityid: {entityid}, entity: {entity}, attribute: {attribute}, old: {old}, new: {new}, kwargs: {kwargs}", prefix=entityid)
            if entityid is not None:
                self._cancel_restart_handle(entityid)
            else:
                #global config has changed
                for eid in self._vacuumdict:
                    # cancel and create new vacuum control handle
                    self._cancel_restart_handle(eid)
        except Exception:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(), prefix=entityid)
        finally:
            self._lock.release()

    def _control_vacuum(self, kwargs):
        # calculate the next start time per vacuum
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._log_debug("entityid: {}".format(entityid))
            # detect current day
            # Return the day of the week as an integer,
            # where Monday is 1 and Sunday is 7
            isoweekdaydict = {1: "monday",
                              2: "tuesday",
                              3: "wednesday",
                              4: "thursday",
                              5: "friday",
                              6: "saturday",
                              7: "sunday"}
            dtime = datetime.now()
            wday = isoweekdaydict.get(dtime.isoweekday(), None)
            self._log_debug("Current isoweekday is {}/{}".format(
                dtime.isoweekday(), wday))
            self._log_debug("input_datetime.control_vacuum_{}_start_time_{}"
                      .format(entityid, wday))
            if wday is not None:
                today = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0)
                # Zeit für das starten des Vacuum bestimmen. 
                vc_start_time = today + timedelta(
                    hours=self.get_state(
                        "input_datetime.control_vacuum_{}_start_time_{}"
                        .format(entityid, wday), attribute="hour"),
                    minutes=self.get_state(
                        "input_datetime.control_vacuum_{}_start_time_{}"
                        .format(entityid, wday), attribute="minute"),
                    seconds=self.get_state(
                        "input_datetime.control_vacuum_{}_start_time_{}"
                        .format(entityid, wday), attribute="second"))
                if vc_start_time < datetime.now():
                    # startzeit ist schon vorbei
                    # Trigger am nächsten Tag neustarten
                    dtime = datetime.now().replace(
                        hour=0, minute=0, second=0,
                        microsecond=0) + timedelta(days=1, seconds=5)
                    self._log_info("Time to start vacuum has passed nexttrigger: {}"
                              .format(dtime))
                    self._set_handle(entityid, "vc_handle", self.run_at(
                        self._control_vacuum,
                        dtime, entityid=entityid))
                else:
                    # start zeit liegt später am Tag
                    self._log_info("Time to start vacuum: {}"
                              .format(vc_start_time))
                    self._set_handle(entityid, "vc_handle", self.run_at(
                        self._start_vacuum,
                        vc_start_time, entityid=entityid))
            else:
                self._log_error("Could not detect current weekday!"
                                "isoweekday: {}".format(dtime.isoweekday()))
        except Exception:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(), prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("Catched Error. Restart at %s" %
                            nexttrigger, prefix=entityid)
            self._set_handle(entityid, "vc_handle", self.run_at(
                self._close_blinds,
                datetime.now() + timedelta(seconds=5), entityid=entityid))
        finally:
            self._lock.release()

    def _start_vacuum(self, kwargs):
        try:
            self._lock.acquire(True)
            entityid = kwargs.get('entityid', None)
            self._set_handle(entityid, "vc_handle", None)
            self._log_info("start vacuum %s" %
                      self._get_variable(entityid, "vacuumID"),
                      prefix=entityid)
            self.call_service("vacuum/start",
                              entity_id=self._get_variable(
                                  entityid, "vacuumID"))
            # Trigger neu starten
            self._log_debug("nexttrigger %s" %
                      (datetime.now() + timedelta(minutes=5)), prefix=entityid)
            self._set_handle(entityid, "vc_handle", self.run_at(
                self._control_vacuum,
                datetime.now() + timedelta(minutes=5),
                entityid=entityid))
        except Exception:
            entityid = kwargs.get('entityid', None)
            self._log_error(traceback.format_exc(), prefix=entityid)
            nexttrigger = datetime.now() + timedelta(seconds=5)
            self._log_error("Catched Error. Restart in %s" %
                            nexttrigger, prefix=entityid)
            self._set_handle(entityid, "vc_handle", self.run_at(
                self._control_vacuum,
                datetime.now() + timedelta(seconds=5),
                entityid=entityid))
        finally:
            self._lock.release()


class VacuumControlConfiguration(BaseClass):
    variables_boolean = {"automatic_control": {
        "name": "Start vacuum automatically",
        "icon": "mdi:robot-vacuum"}
    }
    variables_datetime = {"start_time_monday": {
        "name": "Starttime on monday",
        "icon": "mdi:clock-outline",
        "has_date": False,
        "has_time": True},
        "start_time_tuesday": {
        "name": "Starttime on tuesday",
        "icon": "mdi:clock-outline",
        "has_date": False,
        "has_time": True},
        "start_time_wednesday": {
        "name": "Starttime on wednesday",
        "icon": "mdi:clock-outline",
        "has_date": False,
        "has_time": True},
        "start_time_thursday": {
        "name": "Starttime on thursday",
        "icon": "mdi:clock-outline",
        "has_date": False,
        "has_time": True},
        "start_time_friday": {
        "name": "Starttime on friday",
        "icon": "mdi:clock-outline",
        "has_date": False,
        "has_time": True},
        "start_time_saturday": {
        "name": "Starttime on saturday",
        "icon": "mdi:clock-outline",
        "has_date": False,
        "has_time": True},
        "start_time_sunday": {
        "name": "Starttime on sunday",
        "icon": "mdi:clock-outline",
        "has_date": False,
        "has_time": True},
    }
    variables_number = {}
    variables_boolean_global = {"enable_global": {
        "name": "Enable automatic vacuum control",
        "icon": "mdi:robot-vacuum"},
        "configuration": {
        "name": "Create new config templates"}
    }

    def initialize(self):
        self._lock = Semaphore(1)
        self.cfg_handle = self.listen_state(
            self.update_config_files,
            "input_boolean.control_vacuum_configuration", duration=10)

        if self.get_state(
                "input_boolean.control_vacuum_configuration") is None:
            # variable does not exit, config is created for the first time
            # start config creation
            if self.args["debug"]:
                self._log_debug("input_boolean.control_vacuum_configuration is None")
            self.create_config_files()
        else:
            if self.args["debug"]:
                self._log_debug(
                    "input_boolean.control_vacuum_configuration is not None")

    def update_config_files(self, entity, attribute, old, new, duration):
        if new:
            # deactivate boolean
            self.call_service(
                "input_boolean/turn_off",
                entity_id="input_boolean.control_vacuum_configuration")
            # run config creation
            self.create_config_files()

    def create_config_files(self):
        self._log_debug("create_config_files")
        statedict = self.get_state()
        overwritefiles = True
        idlist = list()
        for entity in statedict:
            if re.match('^vacuum.*', entity, re.IGNORECASE):
                # detected cover
                id = self._getid(statedict, entity)
                idlist.append(id)
                # create all required variables
                # Name convention: <type>.control_vacuum_<id>_<variable>
                # Example Friendly_name
                # input_boolean.control_vacuum_<id>_automatic_control
                # input_datetime.control_vacuum_<id>_start_time_monday
                # input_datetime.control_vacuum_<id>_start_time_tuesday
                # input_datetime.control_vacuum_<id>_start_time_wednesday
                # input_datetime.control_vacuum_<id>_start_time_thursday
                # input_datetime.control_vacuum_<id>_start_time_friday
                # input_datetime.control_vacuum_<id>_start_time_saturday
                # input_datetime.control_vacuum_<id>_start_time_sunday

                # create boolean variabels
                self._writevariables(id, "input_boolean",
                                     self.variables_boolean, overwritefiles)
                self._writevariables(id, "input_datetime",
                                     self.variables_datetime, overwritefiles)
                self._writevariables(id, "input_number",
                                     self.variables_number, overwritefiles)
                self._writeconfiguration(
                    id, {"input_boolean": self.variables_boolean,
                         "input_datetime": self.variables_datetime,
                         "input_number": self.variables_number},
                    overwritefiles)
                overwritefiles = False
            else:
                if self.args["debug"]:
                    self._log_debug("Entity %s does not match." % entity)

        # add global variables
        # input_boolean.control_vacuum_enable_global

        self._writevariables("global", "input_boolean",
                             self.variables_boolean_global, False)
        self._writeconfiguration(
            "global", {"input_boolean": self.variables_boolean_global}, False)
        idlist.append("global")
        self._writeconfigview(idlist, False)

    def _writevariables(self, id, filename, varlist, overwritefiles):
        if id is None:
            id = ""
        # Create Storage path
        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        fileout = open("%s%s%s.yaml_" % (
            dir_path, os.sep, filename), "w" if overwritefiles else "a")
        fileout.write("##Start## %s\n" % id)
        for v in varlist:
            if id != "" and id != "global":
                fileout.write("control_vacuum_%s_%s:\n" % (id, v))
            else:
                fileout.write("control_vacuum_%s:\n" % v)
            elem = varlist.get(v)
            for e in elem:
                fileout.write("  %s: %s\n" % (e, elem.get(e)))
        fileout.write("##End## %s\n\n" % id)
        fileout.close()

    def _writeconfiguration(self, id, vardict, overwritefiles):
        if id is None:
            id = ""
        # Create Storage path
        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        fileout = open("%s%sconfig_vacuum.yaml_" %
                       (dir_path, os.sep), "w" if overwritefiles else "a")
        fileout.write("##Start## %s\n" % id)
        fileout.write("config_vacuum_%s:\n" % id)
        fileout.write("  name: Config vacuum %s\n" % id)
        fileout.write("  view: no\n")
        fileout.write("  entities:\n")
        for k in vardict:
            varlist = vardict.get(k)
            for v in varlist:
                if id != "" and id != "global":
                    fileout.write(
                        "    - %s.control_vacuum_%s_%s\n" % (k, id, v))
                else:
                    fileout.write("    - %s.control_vacuum_%s\n" % (k, v))
        fileout.write("##End## %s\n\n" % id)
        fileout.close()

    def _writeconfigview(self, idlist, overwritefiles):
        # Create Storage path
        path = os.path.abspath(__file__)
        dir_path = os.path.dirname(path)
        fileout = open("%s%sconfig_vacuum.yaml_" %
                       (dir_path, os.sep), "w" if overwritefiles else "a")
        fileout.write("##Start## config_vacuum\n")
        fileout.write("config_vacuum:\n")
        fileout.write("  name: Config Vacuum\n")
        fileout.write("  view: yes\n")
        fileout.write("  entities:\n")
        for id in idlist:
            fileout.write("    - group.config_vacuum_%s\n" % id)
        fileout.write("##End## config_vacuum\n\n")
        fileout.close()
