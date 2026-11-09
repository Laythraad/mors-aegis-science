"""Reproducible local quantum circuit experiments and classical baselines.

All outputs use local Qiskit Aer statevector/shot simulation. No quantum hardware,
cloud service, scientific training corpus, or quantum advantage is claimed.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import threading
import time
import tracemalloc
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np

_TRACE_LOCK = threading.Lock()

MAX_QUBITS = 8
MIN_SHOTS = 128
MAX_SHOTS = 8192
MAX_BENCHMARK_SAMPLES = 128


class QuantumInputError(ValueError):
    pass


def _bloch_vector(state: np.ndarray, qubit: int, n_qubits: int) -> dict[str, float]:
    mask = 1 << qubit
    x = y = z = 0j
    for index, amplitude in enumerate(state):
        partner = index ^ mask
        if not (index & mask):
            left = amplitude.conjugate()
            right = state[partner]
            x += left * right + right.conjugate() * amplitude
            y += -1j * left * right + 1j * right.conjugate() * amplitude
            z += abs(amplitude) ** 2 - abs(state[partner]) ** 2
    return {"x": float(np.real(x)), "y": float(np.real(y)), "z": float(np.real(z))}


def _run_qiskit_aer(n_qubits: int, gates: list[dict[str, Any]], shots: int, seed: int) -> tuple[np.ndarray, dict[str, int], dict[str, Any]]:
    """Run an actual local Qiskit Aer circuit simulation, never hardware execution."""
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator
    circuit = QuantumCircuit(n_qubits, n_qubits)
    for item in gates:
        name = item["gate"]
        if name == "h":
            circuit.h(item["qubit"])
        elif name == "x":
            circuit.x(item["qubit"])
        elif name == "y":
            circuit.y(item["qubit"])
        elif name == "z":
            circuit.z(item["qubit"])
        elif name == "rx":
            circuit.rx(item["angle"], item["qubit"])
        elif name == "ry":
            circuit.ry(item["angle"], item["qubit"])
        elif name == "rz":
            circuit.rz(item["angle"], item["qubit"])
        elif name == "cx":
            circuit.cx(item["control"], item["target"])
        elif name == "cz":
            circuit.cz(item["control"], item["target"])
        elif name == "swap":
            circuit.swap(item["qubit_a"], item["qubit_b"])
    state_circuit = circuit.copy()
    state_circuit.save_statevector()
    measured = circuit.copy()
    measured.measure(range(n_qubits), range(n_qubits))
    simulator = AerSimulator(method="statevector", max_parallel_threads=1)
    compiled_state = transpile(state_circuit, simulator, seed_transpiler=seed)
    compiled_measure = transpile(measured, simulator, seed_transpiler=seed)
    state_result = simulator.run(compiled_state, shots=1, seed_simulator=seed).result()
    count_result = simulator.run(compiled_measure, shots=shots, seed_simulator=seed).result()
    state = np.asarray(state_result.get_statevector(compiled_state), dtype=np.complex128)
    counts = {str(key).replace(" ", "")[::-1]: int(value) for key, value in count_result.get_counts(compiled_measure).items()}
    metadata = {"name": "Qiskit AerSimulator(statevector)", "version": __import__("qiskit_aer").__version__,
                "mode": "local Qiskit Aer classical statevector and shot simulation", "hardware_execution": False,
                "transpiled_state_circuit_depth": int(compiled_state.depth()),
                "transpiled_measurement_circuit_depth": int(compiled_measure.depth()), "method": "statevector"}
    return state, counts, metadata


def _state_summary(state: np.ndarray, n_qubits: int) -> dict[str, Any]:
    probabilities = np.abs(state) ** 2
    probabilities = probabilities / probabilities.sum()
    purity = 1.0
    if n_qubits >= 2:
        # Partial trace on qubit 0, using explicit amplitudes for pure-state bipartition.
        reduced = np.zeros((2, 2), dtype=np.complex128)
        for i, a in enumerate(state):
            for j, b in enumerate(state):
                if (i >> 1) == (j >> 1):
                    reduced[i & 1, j & 1] += a * b.conjugate()
        purity = float(np.real(np.trace(reduced @ reduced)))
    return {
        "statevector": [{"basis": format(i, f"0{n_qubits}b")[::-1], "real": float(a.real), "imag": float(a.imag),
                         "probability": float(probabilities[i])}
                        for i, a in enumerate(state) if abs(a) > 1e-12],
        "probabilities": {format(i, f"0{n_qubits}b")[::-1]: float(p) for i, p in enumerate(probabilities) if p > 1e-12},
        "bloch_vectors": [_bloch_vector(state, q, n_qubits) for q in range(n_qubits)],
        "bipartition_purity_qubit0_vs_rest": purity,
        "is_entangled_across_qubit0_partition": bool(n_qubits >= 2 and purity < 1 - 1e-9),
        "normalization_sum": float(probabilities.sum()),
    }


def _simulate_statevector(n_qubits: int, gates: list[dict[str, Any]]) -> np.ndarray:
    """Small, transparent NumPy state-vector engine for at most 8 qubits."""
    size = 1 << n_qubits
    state = np.zeros(size, dtype=np.complex128)
    state[0] = 1.0
    for gate in gates:
        name = gate["gate"]
        if name == "h":
            qubit = gate["qubit"]
            for idx in range(size):
                if not idx & (1 << qubit):
                    j = idx | (1 << qubit)
                    a, b = state[idx], state[j]
                    state[idx], state[j] = (a + b) / math.sqrt(2), (a - b) / math.sqrt(2)
        elif name in {"x", "y", "z"}:
            qubit = gate["qubit"]
            mask = 1 << qubit
            if name == "x":
                for idx in range(size):
                    if not idx & mask:
                        j = idx | mask
                        state[idx], state[j] = state[j], state[idx]
            elif name == "z":
                for idx in range(size):
                    if idx & mask:
                        state[idx] = -state[idx]
            else:
                for idx in range(size):
                    if not idx & mask:
                        j = idx | mask
                        a, b = state[idx], state[j]
                        state[idx], state[j] = -1j * b, 1j * a
        elif name in {"rx", "ry", "rz"}:
            qubit = gate["qubit"]
            angle = float(gate["angle"])
            c, s = math.cos(angle / 2), math.sin(angle / 2)
            if name == "rx":
                matrix = np.array([[c, -1j*s], [-1j*s, c]])
            elif name == "ry":
                matrix = np.array([[c, -s], [s, c]])
            else:
                matrix = np.diag([np.exp(-1j*angle/2), np.exp(1j*angle/2)])
            mask = 1 << qubit
            for idx in range(size):
                if not idx & mask:
                    j = idx | mask
                    a, b = state[idx], state[j]
                    state[idx], state[j] = matrix[0, 0]*a + matrix[0, 1]*b, matrix[1, 0]*a + matrix[1, 1]*b
        elif name == "cx":
            control, target = gate["control"], gate["target"]
            for idx in range(size):
                if idx & (1 << control) and not idx & (1 << target):
                    j = idx | (1 << target)
                    state[idx], state[j] = state[j], state[idx]
        elif name == "cz":
            control, target = gate["control"], gate["target"]
            for idx in range(size):
                if idx & (1 << control) and idx & (1 << target):
                    state[idx] = -state[idx]
        elif name == "swap":
            a, b = gate["qubit_a"], gate["qubit_b"]
            for idx in range(size):
                abit, bbit = bool(idx & (1 << a)), bool(idx & (1 << b))
                if abit != bbit:
                    other = idx ^ (1 << a) ^ (1 << b)
                    if idx < other:
                        state[idx], state[other] = state[other], state[idx]
        else:
            raise QuantumInputError(f"Unsupported gate: {name}")
    norm = float(np.linalg.norm(state))
    if not math.isfinite(norm) or abs(norm - 1) > 1e-9:
        raise QuantumInputError("Circuit state failed normalization check")
    return state


def _validated_circuit(payload: dict[str, Any]) -> tuple[int, int, list[dict[str, Any]]]:
    def integer(name: str, default: int) -> int:
        value = payload.get(name, default)
        if type(value) is not int:
            raise QuantumInputError(f"{name} must be an integer")
        return value
    n = integer("n_qubits", 2)
    shots = integer("shots", 2048)
    seed = integer("seed", 41)
    if not 1 <= n <= MAX_QUBITS:
        raise QuantumInputError(f"n_qubits must be between 1 and {MAX_QUBITS}")
    if not MIN_SHOTS <= shots <= MAX_SHOTS:
        raise QuantumInputError(f"shots must be between {MIN_SHOTS} and {MAX_SHOTS}")
    if not 0 <= seed <= 2**32 - 1:
        raise QuantumInputError("seed must be an unsigned 32-bit integer")
    gates = payload.get("gates")
    if not isinstance(gates, list) or len(gates) > 64:
        raise QuantumInputError("gates must be a list containing at most 64 operations")
    allowed = {"h", "x", "y", "z", "rx", "ry", "rz", "cx", "cz", "swap"}
    normalized = []
    for index, raw in enumerate(gates):
        if not isinstance(raw, dict) or raw.get("gate") not in allowed:
            raise QuantumInputError(f"gate {index} is unsupported")
        gate = dict(raw)
        name = gate["gate"]
        if name in {"cx", "cz"}:
            control, target = gate.get("control"), gate.get("target")
            if type(control) is not int or type(target) is not int or control == target or min(control, target) < 0 or max(control, target) >= n:
                raise QuantumInputError(f"gate {index} needs distinct in-range control and target qubits")
        elif name == "swap":
            a, b = gate.get("qubit_a"), gate.get("qubit_b")
            if type(a) is not int or type(b) is not int or a == b or min(a, b) < 0 or max(a, b) >= n:
                raise QuantumInputError(f"gate {index} needs distinct in-range qubit_a and qubit_b")
        else:
            q = gate.get("qubit")
            if type(q) is not int or not 0 <= q < n:
                raise QuantumInputError(f"gate {index} needs an in-range qubit")
            if name in {"rx", "ry", "rz"}:
                angle = gate.get("angle")
                if type(angle) not in (int, float) or not math.isfinite(float(angle)) or abs(float(angle)) > 2*math.pi:
                    raise QuantumInputError(f"gate {index} angle must be finite and within [-2π, 2π]")
                gate["angle"] = float(angle)
        normalized.append(gate)
    return n, shots, normalized


def run_circuit(payload: dict[str, Any]) -> dict[str, Any]:
    n, shots, gates = _validated_circuit(payload)
    seed = payload.get("seed", 41)
    digest = hashlib.sha256(json.dumps({"n_qubits": n, "gates": gates, "shots": shots, "seed": seed}, sort_keys=True).encode()).hexdigest()
    with _TRACE_LOCK:
        tracemalloc.start()
        start = time.perf_counter()
        try:
            try:
                state, histogram, backend = _run_qiskit_aer(n, gates, shots, seed)
                state_seconds = time.perf_counter() - start
            except ImportError:
                state = _simulate_statevector(n, gates)
                state_seconds = time.perf_counter() - start
                probabilities = np.abs(state) ** 2
                outcomes = np.arange(1 << n)
                sampled = np.random.default_rng(seed).choice(outcomes, size=shots, p=probabilities)
                unique, counts = np.unique(sampled, return_counts=True)
                histogram = {format(int(k), f"0{n}b")[::-1]: int(v) for k, v in zip(unique, counts)}
                backend = {"name": "NumPy reference statevector", "mode": "local classical simulation of quantum circuit", "hardware_execution": False}
            summary = _state_summary(state, n)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    result_id = str(uuid.uuid4())
    return {"experiment_id": result_id, "experiment_type": "quantum_circuit_simulation", "evidence_class": "COMPUTED RESULTS",
            "backend": backend,
            "parameters": {"n_qubits": n, "shots": shots, "seed": seed, "gates": gates},
            "state": summary, "counts": histogram, "resources": {"statevector_runtime_ms": round(state_seconds*1000, 6), "measurement_runtime_inclusive_of_state_ms": round((time.perf_counter()-start)*1000, 6),
                                                                        "python_tracemalloc_peak_bytes": peak, "statevector_complex128_bytes": (1<<n)*16},
            "reproducibility": {"input_sha256": digest, "seed": seed, "python": platform.python_version(), "numpy": np.__version__},
            "validation": {"state_normalization": summary["normalization_sum"], "counts_sum": sum(histogram.values()), "counts_match_shots": sum(histogram.values()) == shots},
            "limitations": ["No quantum hardware was used; this is classical simulation of a quantum circuit.",
                            "Statevector memory and runtime grow exponentially with qubit count.",
                            "Measurement frequencies are seeded finite-shot samples from ideal probabilities; noise, calibration and hardware latency are not modeled.",
                            "Single-qubit Bloch vectors are reduced-state expectations; a maximally entangled qubit has a mixed reduced state."],
            "created_at": datetime.now(timezone.utc).isoformat()}


def _feature_map_angles(x: list[float]) -> list[float]:
    if len(x) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 10 for v in x):
        raise QuantumInputError("each QML sample must have two finite features in [-10, 10]")
    return [float(v) for v in x]


def _quantum_kernel(x: list[float], y: list[float]) -> float:
    a, b = _feature_map_angles(x), _feature_map_angles(y)
    # Two-qubit feature-map overlap: |<phi(y)|phi(x)>|^2 for
    # H-RZ(x_i)-CZ-RZ(x0*x1) with a second-order data re-upload phase.
    def state(values: list[float]) -> np.ndarray:
        gates = [{"gate":"h", "qubit":0}, {"gate":"h", "qubit":1},
                 {"gate":"rz", "qubit":0, "angle":values[0]},
                 {"gate":"rz", "qubit":1, "angle":values[1]},
                 {"gate":"cz", "control":0, "target":1},
                 {"gate":"rz", "qubit":1, "angle":(math.pi-values[0])*(math.pi-values[1])},
                 {"gate":"rz", "qubit":0, "angle":values[0]},
                 {"gate":"rz", "qubit":1, "angle":values[1]}]
        return _simulate_statevector(2, gates)
    return float(abs(np.vdot(state(b), state(a)))**2)


def run_kernel_benchmark(payload: dict[str, Any]) -> dict[str, Any]:
    dataset = payload.get("samples")
    labels = payload.get("labels")
    if not isinstance(dataset, list) or not isinstance(labels, list) or len(dataset) != len(labels) or not 4 <= len(dataset) <= MAX_BENCHMARK_SAMPLES:
        raise QuantumInputError(f"samples and labels must have equal length between 4 and {MAX_BENCHMARK_SAMPLES}")
    if any(not isinstance(row, list) for row in dataset):
        raise QuantumInputError("each sample must be a two-value array")
    x = [_feature_map_angles(list(row)) for row in dataset]
    if any(type(v) is not int for v in labels):
        raise QuantumInputError("labels must be integers 0 or 1")
    y = labels
    if len(set(y)) != 2 or any(v not in (0, 1) for v in y):
        raise QuantumInputError("labels must contain both binary classes 0 and 1")
    seed = payload.get("seed", 41)
    if type(seed) is not int:
        raise QuantumInputError("seed must be an integer")
    if not 0 <= seed <= 2**32-1:
        raise QuantumInputError("seed must be an unsigned 32-bit integer")
    start = time.perf_counter()
    kernel = np.asarray([[_quantum_kernel(a,b) for b in x] for a in x])
    quantum_seconds = time.perf_counter()-start
    eigenvalues = np.linalg.eigvalsh(kernel)
    if eigenvalues.min() < -1e-8:
        raise QuantumInputError("Computed kernel is not positive semidefinite within tolerance")
    # Deterministic leave-one-out kernel ridge classifier.
    alpha = 1e-3
    predictions = []
    start_classical = time.perf_counter()
    for i in range(len(x)):
        keep = [j for j in range(len(x)) if j != i]
        y_train = np.asarray([2*y[j]-1 for j in keep], dtype=float)
        k_train = kernel[np.ix_(keep, keep)]
        coeff = np.linalg.solve(k_train + alpha*np.eye(len(keep)), y_train)
        score = float(kernel[i, keep] @ coeff)
        predictions.append(1 if score >= 0 else 0)
    quantum_classifier_seconds = time.perf_counter()-start_classical
    quantum_accuracy = sum(a == b for a,b in zip(predictions,y))/len(y)
    # Classical radial-basis kernel with deterministic standardization; same
    # leave-one-out protocol, same samples and labels.
    array = np.asarray(x, dtype=float)
    std = array.std(axis=0)
    standardized = (array-array.mean(axis=0))/np.where(std>1e-12,std,1.0)
    distances = ((standardized[:,None,:]-standardized[None,:,:])**2).sum(axis=2)
    gamma = 1.0 / max(1, standardized.shape[1])
    classical_kernel = np.exp(-gamma*distances)
    classical_predictions=[]
    for i in range(len(x)):
        keep=[j for j in range(len(x)) if j!=i]
        coeff=np.linalg.solve(classical_kernel[np.ix_(keep,keep)]+alpha*np.eye(len(keep)),np.asarray([2*y[j]-1 for j in keep],dtype=float))
        classical_predictions.append(1 if float(classical_kernel[i,keep]@coeff)>=0 else 0)
    classical_accuracy=sum(a==b for a,b in zip(classical_predictions,y))/len(y)
    payload_hash=hashlib.sha256(json.dumps({"samples":x,"labels":y,"seed":seed},sort_keys=True).encode()).hexdigest()
    return {"experiment_id":str(uuid.uuid4()),"experiment_type":"quantum_kernel_vs_classical_rbf_leave_one_out","evidence_class":"COMPUTED RESULTS",
            "dataset":{"source":"caller-provided feature matrix","sample_count":len(x),"feature_count":2,"labels":y,"source_authenticity":"not verified"},
            "quantum_simulation":{"kernel":"two-qubit ideal statevector feature-map fidelity kernel","kernel_matrix":kernel.round(8).tolist(),"kernel_eigenvalue_min":float(eigenvalues.min()),
                                  "loo_accuracy":quantum_accuracy,"predictions":predictions,"kernel_build_runtime_ms":round(quantum_seconds*1000,6),"loo_runtime_ms":round(quantum_classifier_seconds*1000,6),"backend":"NumPy statevector circuit simulation; no QPU"},
            "classical_baseline":{"kernel":"standardized RBF (gamma=1/features)","loo_accuracy":classical_accuracy,"predictions":classical_predictions,
                                  "total_runtime_ms":round((time.perf_counter()-start_classical)*1000,6)},
            "comparison":{"accuracy_difference_quantum_minus_classical":quantum_accuracy-classical_accuracy,
                          "quantum_superiority_claimed":False,"interpretation":"Small deterministic demonstration dataset; accuracy differences are not evidence of quantum advantage.",
                          "reliability":"leave-one-out on one small dataset; no repeated-split confidence interval"},
            "reproducibility":{"seed":seed,"input_sha256":payload_hash,"kernel_regularization":alpha,"scaler":"training-free global standardization for this benchmark demonstration",
                               "python":platform.python_version(),"numpy":np.__version__},
            "limitations":["Tiny caller-provided demonstration dataset, not NASA combustion, FIRMS, or astronaut telemetry.",
                           "Ideal statevector simulation performs classical computation and incurs no hardware noise or queue latency.",
                           "This benchmark is pedagogical and not evidence of quantum advantage or QML scalability."],
            "created_at":datetime.now(timezone.utc).isoformat()}
