from app.quantum import QuantumInputError, run_circuit, run_kernel_benchmark


def test_bell_pair_statevector_and_seeded_measurement_are_reproducible():
    payload = {"n_qubits": 2, "shots": 2048, "seed": 17,
               "gates": [{"gate":"h","qubit":0}, {"gate":"cx","control":0,"target":1}]}
    first = run_circuit(payload)
    second = run_circuit(payload)
    assert first["backend"]["hardware_execution"] is False
    assert first["backend"]["name"].startswith("Qiskit AerSimulator")
    assert first["counts"] == second["counts"]
    assert first["state"]["normalization_sum"] == 1.0
    assert set(first["counts"]).issubset({"00", "11"})
    assert sum(first["counts"].values()) == 2048
    assert first["state"]["is_entangled_across_qubit0_partition"] is True
    assert abs(first["state"]["bipartition_purity_qubit0_vs_rest"] - 0.5) < 1e-8
    assert first["reproducibility"]["input_sha256"] == second["reproducibility"]["input_sha256"]


def test_single_qubit_hadamard_has_expected_probabilities_and_bloch_vector():
    result = run_circuit({"n_qubits":1,"shots":2048,"seed":7,"gates":[{"gate":"h","qubit":0}]})
    probs=result["state"]["probabilities"]
    assert abs(probs["0"]-0.5) < 1e-12
    assert abs(probs["1"]-0.5) < 1e-12
    bloch=result["state"]["bloch_vectors"][0]
    assert abs(bloch["x"]-1.0) < 1e-12
    assert abs(bloch["z"]) < 1e-12


def test_invalid_quantum_gate_arguments_are_rejected():
    try:
        run_circuit({"n_qubits":2,"shots":128,"seed":1,"gates":[{"gate":"cx","control":0,"target":0}]})
    except QuantumInputError as error:
        assert "distinct" in str(error)
    else:
        raise AssertionError("identical control and target should be rejected")


def test_quantum_kernel_benchmark_is_controlled_and_does_not_claim_advantage():
    payload={"seed":41,"samples":[[-1,-.8],[-.7,-1.2],[.8,1],[1.2,.7],[-1.1,-.5],[.5,1.3],[.9,.5],[-.4,-.9]],"labels":[0,0,1,1,0,1,1,0]}
    result=run_kernel_benchmark(payload)
    assert len(result["quantum_simulation"]["kernel_matrix"]) == len(payload["samples"])
    assert abs(result["quantum_simulation"]["kernel_eigenvalue_min"]) < 1e-7 or result["quantum_simulation"]["kernel_eigenvalue_min"] > 0
    assert result["comparison"]["quantum_superiority_claimed"] is False
    assert 0 <= result["quantum_simulation"]["loo_accuracy"] <= 1
    assert 0 <= result["classical_baseline"]["loo_accuracy"] <= 1
