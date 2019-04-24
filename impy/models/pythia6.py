'''
Created on 19.01.2015

@author: afedynitch
'''

import numpy as np
from impy.common import MCRun, MCEvent, impy_config, pdata
from impy.util import standard_particles, info


class PYTHIAEvent(MCEvent):
    """Wrapper class around HEPEVT particle stack."""

    def __init__(self, lib, event_kinematics, event_frame):
        # HEPEVT (style) common block
        evt = lib.hepevt

        # Save selector for implementation of on-demand properties
        px, py, pz, en, m = evt.phep
        vx, vy, vz, vt = evt.vhep

        self.charge_vec = None

        MCEvent.__init__(
            self,
            lib=lib,
            event_kinematics=event_kinematics,
            event_frame=event_frame,
            nevent=evt.nevhep,
            npart=evt.nhep,
            p_ids=evt.idhep,
            status=evt.isthep,
            px=px,
            py=py,
            pz=pz,
            en=en,
            m=m,
            vx=vx,
            vy=vy,
            vz=vz,
            vt=vt,
            pem_arr=evt.phep,
            vt_arr=evt.vhep)

    def filter_final_state(self):
        self.selection = np.where(self.status == 1)
        self._apply_slicing()

    def filter_final_state_charged(self):
        self.selection = np.where((self.status == 1) & (self.charge != 0))
        self._apply_slicing()

    @property
    def parents(self):
        if self._is_filtered:
            raise Exception(
                'Parent indices do not point to the' +
                ' proper particles if any slicing/filtering is applied.')
        return self.lib.hepevt.jmohep

    @property
    def children(self):
        if self._is_filtered:
            raise Exception(
                'Parent indices do not point to the' +
                ' proper particles if any slicing/filtering is applied.')
        return self.lib.hepevt.jdahep

    @property
    def charge(self):
        if self.charge_vec is None:
            self.charge_vec = [
                self.lib.pychge(self.lib.pyjets.k[i, 1]) / 3
                for i in xrange(self.npart)
            ]
        return self.charge_vec[self.selection]

class PYTHIA6Run(MCRun):
    """Implements all abstract attributes of MCRun for the 
    EPOS-LHC series of event generators."""

    def sigma_inel(self):
        """Inelastic cross section according to current
        event setup (energy, projectile, target)"""
        return self.lib.pyint7.sigt[0, 0, 5]

    def set_event_kinematics(self, event_kinematics):
        """Set new combination of energy, momentum, projectile
        and target combination for next event."""
        k = event_kinematics
        self._curr_event_kin = k
        self.p1_type = pdata.name(k.p1pdg)
        self.p2_type = pdata.name(k.p2pdg)
        self.ecm = k.ecm
        self.lib.pyinit('CMS', self.p1_type, self.p2_type, self.ecm)
        info(5, 'Setting event kinematics')

    def attach_log(self):
        """Routes the output to a file or the stdout."""
        fname = impy_config['output_log']
        if fname == 'stdout':
            lun = 6
            info(5, 'Output is routed to stdout.')
        else:
            lun = self._attach_fortran_logfile(fname)
            info(5, 'Output is routed to', fname, 'via LUN', lun)

        self.lib.pydat1.mstu[10] = lun

    def init_generator(self, event_kinematics, seed='random'):
        from random import randint

        self._abort_if_already_initialized()

        if seed == 'random':
            seed = randint(1000000, 10000000)
            sseed = str(seed)
            self.lib.pydatr.mrpy[:4] = int(sseed[0:2]), int(sseed[2:4]), \
                int(sseed[4:6]), int(sseed[6:])
        else:
            seed = int(seed)
        info(5, 'Using seed:', seed)
        
        
        if impy_config['pythia6']['new_mpi']:
            # Latest Pythia 6 is tune 383
            self.lib.pytune(383)
            self.event_call = self.lib.pyevnw
        else:
            self.event_call = self.lib.pyevnt
        
        self.lib.pysubs.msel = 2
        self.set_event_kinematics(event_kinematics)

        # Set default stable
        self._define_default_fs_particles()
        self.set_event_kinematics(event_kinematics)


    def set_stable(self, pdgid, stable=True):
        kc = self.lib.pycomp(pdgid)
        if stable:
            self.lib.pydat3.mdcy[kc - 1, 0] = 0
            info(5, 'defining', pdgid, 'as stable particle')
        else:
            self.lib.pydat3.mdcy[kc - 1, 0] = 1
            info(5, pdgid, 'allowed to decay')

    def generate_event(self):
        self.event_call()
        return False