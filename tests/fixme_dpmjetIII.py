from functools import lru_cache

import numpy as np
import pytest
from numpy.testing import assert_allclose
from particle import literals as lp

from chromo.constants import GeV
from chromo.kinematics import CenterOfMass
from chromo.models import DpmjetIII191, DpmjetIII193, EposLHC

from .util import (
    reference_charge,
    run_in_separate_process,
)


def run_pp_collision(model):
    evt_kin = CenterOfMass(10 * GeV, "proton", "proton")
    m = model(evt_kin, seed=4)
    m.set_stable(lp.pi_0.pdgid, True)
    for event in m(1):
        pass
    return event


def run_ab_collision(model):
    evt_kin = CenterOfMass(10 * GeV, (4, 2), (12, 6))
    m = model(evt_kin, seed=1)
    for event in m(1):
        pass
    return event


@pytest.fixture
@pytest.mark.parametrize("model", (DpmjetIII191, DpmjetIII193))
@lru_cache(maxsize=1)
def event(model):
    return run_in_separate_process(run_pp_collision, model)


@pytest.fixture
@pytest.mark.parametrize("model", (DpmjetIII191, DpmjetIII193))
@lru_cache(maxsize=1)
def event_ion(model):
    return run_in_separate_process(run_ab_collision, model)


def test_impact_parameter(event, event_ion):
    # DPMJET defines an impact parameter also for pp
    assert event.impact_parameter > 0
    assert event_ion.impact_parameter > 0


def test_n_wounded(event):
    # TODO Pythia8 returns (0, 0) for pp collision, perhaps unify the response
    assert event.n_wounded == (1, 1)


@pytest.mark.xfail(reason="FIXME: n_wounded always seems to return (1, 1) for DPMJET")
def test_n_wounded_ion(event_ion):
    assert event_ion.n_wounded[0] > 1
    assert event_ion.n_wounded[1] > 1


def run_cross_section(model, p1, p2):
    evt_kin = CenterOfMass(10 * GeV, p1, p2)
    m = model(evt_kin, seed=1)
    return m.cross_section()


@pytest.mark.parametrize("model", (DpmjetIII191, DpmjetIII193))
def test_cross_section(model):
    c = run_in_separate_process(run_cross_section, model, "p", "p")
    assert_allclose(c.total, 38.2, atol=0.1)
    assert_allclose(c.inelastic, 30.7, atol=0.1)
    assert_allclose(c.elastic, 7.4, atol=0.1)
    assert_allclose(c.diffractive_xb, 1.6, atol=0.1)
    assert_allclose(c.diffractive_ax, 1.6, atol=0.1)
    assert_allclose(c.diffractive_xx, 9.9, atol=0.1)
    assert c.diffractive_axb == 0
    assert_allclose(
        c.non_diffractive,
        c.inelastic - c.diffractive_xb - c.diffractive_ax - c.diffractive_xx,
    )


def test_charge(event):
    expected = reference_charge(event.pid)
    # skip internal particles unknown to reference_charge
    ma = np.isnan(expected)
    # EPOS has lots of unknown generator-specific particles.
    # For these, NaN is returned. We just check here whether
    # the fraction is not 100 %, that cannot be, since at least
    # final state particles cannot be generator-specific.
    assert np.mean(ma) < 0.8
    event.charge[ma] = np.nan
    assert_allclose(event.charge, expected)


def test_vertex(event):
    assert np.sum(event.vt != 0) > 0


def test_daughters(event):
    assert event.daughters.shape == (len(event), 2)
    # some particles have no daughters
    assert sum(x[0] == 0 and x[1] == 0 for x in event.daughters) > 0

    # somes particles have single daughters (elastic scattering in parton shower)
    assert sum(x[0] > 0 and x[1] == 0 for x in event.daughters) > 0

    # some particles have multiple daughters
    assert sum(x[0] > 0 and x[1] > 0 for x in event.daughters) > 0


def test_mothers(event):
    assert event.mothers.shape == (len(event), 2)
    # same particles have no mothers
    assert sum(x[0] == 0 and x[1] == 0 for x in event.mothers) > 0

    # most particles have a single mother
    assert sum(x[0] > 0 and x[1] == 0 for x in event.mothers) > 0

    # some particles have multiple mothers
    assert sum(x[0] > 0 and x[1] > 0 for x in event.mothers) > 0


def run_set_stable(stable):
    evt_kin = CenterOfMass(10 * GeV, "proton", "proton")
    m = EposLHC(evt_kin, seed=4)
    for pid, s in stable.items():
        m.set_stable(pid, s)
    for event in m(1):
        pass
    return event


def test_set_stable():
    pid = lp.pi_0.pdgid
    ev1 = run_in_separate_process(run_set_stable, {pid: True})
    ev2 = run_in_separate_process(run_set_stable, {pid: False})

    # ev1 contains final state pi0
    assert np.any(ev1.pid[ev1.status == 1] == pid)

    # ev2 does not contains final state pi0
    assert np.all(ev2.pid[ev2.status == 1] != pid)
