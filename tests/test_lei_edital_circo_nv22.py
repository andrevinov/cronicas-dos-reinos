from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import politica_civica as civic
from test_politica_civica_nv22 import CivicPolicyFixture


class CivicCircusAcceptanceTest(CivicPolicyFixture):
    def test_lei_legitima_pode_ser_publicada_no_circo_sem_lei_aleatoria(self):
        proposal = self.propose(
            measure_type="lei",
            title="Lei de segurança de estruturas públicas",
            motive="Regulamentar uma condição urbana identificada.",
            institutional_cause="Deliberação expressa do gabinete na fixture.",
        )
        measure_id = proposal["medida"]
        state = proposal["deltas"][0]["valor"]
        approved = civic.propose_transition(
            self.repo, measure_id=measure_id, target_phase="aprovada",
            when=self.when("10:00"), reason="Lei aprovada.", state=state,
        )
        state = approved["deltas"][0]["valor"]
        effective = civic.propose_transition(
            self.repo, measure_id=measure_id, target_phase="vigente",
            when=self.when("11:00"), reason="Lei entrou em vigência.", state=state,
        )
        state = effective["deltas"][0]["valor"]
        publication = civic.propose_publication(
            self.repo, measure_id=measure_id, locality="circo", period="persistente",
            channel="edital_publico", content="A lei passa a vigorar em Ravens Bluff.",
            when=self.when("12:00"), state=state,
        )
        projected = civic.project_for_permanence(
            self.repo, locality="circo", date="21 Eleasis, 1372 DR", period="tarde",
            state=publication["deltas"][0]["valor"],
        )
        self.assertEqual(len(projected["avisos"]), 1)
        self.assertEqual(projected["avisos"][0]["medida"], measure_id)


if __name__ == "__main__":
    unittest.main()
