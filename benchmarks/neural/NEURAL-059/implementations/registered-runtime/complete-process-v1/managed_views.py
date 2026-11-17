"""Exact original CalibrationViews class with owner-managed I/O imports only."""
from copy import deepcopy
from .scientific.contracts import need, pin, canonical, CONDITIONS, STATUS, check_prepared
from .managed_io import OwnedDirectory

class CalibrationViews:
    """Fresh separate session x F/I x condition roots; never all sessions in an actor root."""
    def __init__(self, path, sessions, members, project_case, frozen_F_sources, max_bytes):
        check_prepared(sessions,members)
        need(set(frozen_F_sources)==set(CONDITIONS) and all(type(x) is bytes and x
             for x in frozen_F_sources.values()),"actual global F source bodies before values")
        self.parent=OwnedDirectory(path,max_bytes)
        self.records=[];self.actor_commits={};self.max_bytes=max_bytes
        self.source_pins={c:pin(b) for c,b in frozen_F_sources.items()}
        self.total=0;self.poisoned=False;self.children={}
        try:
            for session in sessions:
                sid=session["session_id"]
                sid_name=pin(sid)["sha256"][:24]
                for arm in ("F","I"):
                    for condition in CONDITIONS:
                        childpath=self.parent.path/(arm+"-"+condition+"-"+sid_name)
                        with OwnedDirectory(childpath,max_bytes) as child:
                            self.children[(sid,arm,condition)]={"path":str(childpath),
                                "identity":child.root_stamp}
                            if arm=="F":
                                self._write(child,"frozen_source.txt",frozen_F_sources[condition])
                            splits={split:[project_case(deepcopy(c),condition,include_label=True)
                                for c in session["cases"] if c["split"]==split]
                                for split in ("train","val")}
                            body=canonical({"status":STATUS,"arm":arm,"condition":condition,
                                "session_id":sid,"calibration":splits,"future_query_files":False,
                                "F_source_precedes_values":self.source_pins[condition]})
                            published=self._write(child,"calibration.json",body)
                            self.records.append({"session_id":sid,"arm":arm,"condition":condition,
                                "directory":str(childpath),"calibration":published})
            manifest=canonical({"status":STATUS,"views":self.records,
                "actor_mount_isolation_qualified":False})
            self.total+=len(manifest);need(self.total<=max_bytes,"complete view manifest allowance")
            self.parent.write("VIEW_MANIFEST.json",manifest)
        except BaseException:
            self.poisoned=True;self.close();raise

    def _write(self,child,name,body):
        self.total+=len(body)
        need(self.total<=self.max_bytes,"complete attempted calibration write budget")
        return child.write(name,body)

    def commit_actor(self, session_id, arm, condition, source_body, config_body, learned_state_body):
        key=(session_id,arm,condition)
        need(not self.poisoned and key in self.children and key not in self.actor_commits,
             "one source/config/state freeze per session/arm/condition")
        need(all(type(b) is bytes and b for b in (source_body,config_body,learned_state_body)),
             "actual actor source/config/state bytes")
        child_info=self.children[key]
        try:
            self.parent.check()
            with OwnedDirectory.attach(child_info["path"],self.max_bytes,child_info["identity"]) as child:
                if arm=="F":
                    need(pin(source_body)==self.source_pins[condition],"unchanged F source before calibration")
                    source=pin(child.read_exact("frozen_source.txt",self.source_pins[condition]))
                else:source=self._write(child,"selected_source.txt",source_body)
                captured={"source":source,"configuration":self._write(child,"selected_config.txt",config_body),
                          "state":self._write(child,"selected_state.txt",learned_state_body)}
                need(captured=={"source":pin(source_body),"configuration":pin(config_body),
                                "state":pin(learned_state_body)},"actual durable actor bodies before held route")
                self.actor_commits[key]=captured
            return deepcopy(captured)
        except BaseException:
            self.poisoned=True;raise

    def close(self):
        self.parent.close()
