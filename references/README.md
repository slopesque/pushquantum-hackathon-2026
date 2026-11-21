# Qoro × PushQuantum Hackathon: notebook kit

Choose one of two [QOBLIB](https://github.com/ZIB-AOPT/QOBLIB) benchmark problems, push it to the
largest instance you can and get as close as you can to the best published results, or beat them,
using problem partitioning with [Divi](https://github.com/QoroQuantum/divi) on Qoro's cloud.

**Step one: [sign up at dash.qoroquantum.net](https://dash.qoroquantum.net)** for your API key and
hackathon credits.

## The notebooks

| Notebook | What it is |
|---|---|
| [`00_main_qubo_101.ipynb`](00_main_qubo_101.ipynb)<br>[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/QoroQuantum/pushquantum-hackathon-2026/blob/main/00_main_qubo_101.ipynb) | **Start here.** Part 0: API key, install, backend. Part 1, QUBO 101 with Divi: build a QUBO, characterize and validate it, QAOA blind and warm-started, PCE, partitioning. Part 2: choose your problem, run it in Colab, hand in. |
| [`01_portfolio_optimisation.ipynb`](01_portfolio_optimisation.ipynb)<br>[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/QoroQuantum/pushquantum-hackathon-2026/blob/main/01_portfolio_optimisation.ipynb) | QOBLIB 06, multi-period portfolio optimisation: official model → QUBO → classical baseline → PCE and partitioned QAOA → solution file. 58 to about 36 000 binary variables. |
| [`02_network_design.ipynb`](02_network_design.ipynb)<br>[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/QoroQuantum/pushquantum-hackathon-2026/blob/main/02_network_design.ipynb) | QOBLIB 08, network design: topology QUBO with Divi `LinearConstraint`s + exact routing LP → sample, score, write a solution file. 20 to 552 binary variables. |

**Run order:** 00 first, then **one** of 01 or 02. Setup is explained only in notebook 00 and in this
README; the problem notebooks repeat the setup code without the explanations.

**How the winner is chosen:** the scale you reach, and the quality of your solution (QOBLIB's official
objective) compared with the best results published on QOBLIB. [Scoring](#scoring) explains how a
solution is scored, and notebook 00, *Handing in*, says what to hand in.

## Running in Google Colab

1. **Open a notebook** with its *Open in Colab* badge above.
2. **API key.** In Colab's left sidebar, click the key icon, add a secret named `QORO_API_KEY` with your
   key as its value, and switch on notebook access. Secrets belong to your Google account, so you add it
   once and switch on access in each notebook.
3. **Install.** Run the notebook's first setup cell. It installs Divi 0.16.2 if it is missing; if it
   installs anything, restart the session (Runtime → Restart session) and run from the top. Notebooks 01
   and 02 also download the helper file `qoblib_tools.py` in their setup.
4. **To keep your changes,** save a copy to your Drive (File → Save a copy in Drive).

Instance data and the `.sol` files you write land in `/content` and disappear when the session ends:
download what you want to keep.

## Running locally

```bash
git clone https://github.com/QoroQuantum/pushquantum-hackathon-2026.git
cd pushquantum-hackathon-2026
pip install "qoro-divi[qubo-decompose,jupyter]==0.16.2"
```

Divi 0.16.2 needs Python 3.11 or newer. The version is pinned because names can change between Divi's
minor versions. Put your key in a file called `.env` next to the notebooks, containing
`QORO_API_KEY="your_api_key_here"`. The repository's `.gitignore` keeps `.env` out of commits.

Optional: Maestro, Qoro's simulator, as a drop-in for code you write directly in Qiskit
(`pip install qiskit-maestro`) or PennyLane (`pip install pennylane-maestro`).

Without a key, everything runs on the local simulator, and cells that need the cloud (the
Characterization Service) print "Skipped".

## The helper file

`qoblib_tools.py` holds instance loaders, the **official scorers**, QUBO builders and solution-file
writers for portfolio optimisation and network design. The scorers are Python ports of QOBLIB's own
checkers and match every published reference solution. It is the referee, so don't edit it. Instance
data is downloaded from QOBLIB's GitHub repository on first use and cached in `qoblib_data/` next to the
helper file.

## Solution files

Solution files use QOBLIB's own formats, and the problem notebooks write them for you:

* **Portfolio optimisation:** QOBLIB's
  [canonical format](https://github.com/ZIB-AOPT/QOBLIB/blob/main/06-portfolio/check/README.md#canonical-solution-format),
  named `<instance>_b<budget>_l<lambda>.sol`, for example `po_a010_t10_orig_b004_l1e-4.sol`. Keep its
  `instance`, `budget` and `lambda` header lines.
* **Network design:** QOBLIB's
  [Gurobi-style format](https://github.com/ZIB-AOPT/QOBLIB/blob/main/08-network/check/README.md#input-format),
  named `network<NN>.sol`, for example `network12.sol`. The file name says which instance it solves.

The referee recomputes the objective from the positions or flows in the file, so the value written in the
file doesn't count. Notebook 00, *Handing in*, lists what else to hand in.

## Scoring

The referee in `qoblib_tools.py` scores each solution from its `.sol` file, the same way QOBLIB's own
checkers do. A solution that breaks a rule doesn't count. For both problems, a lower score is better.

| Problem | Rules the referee checks | Score |
|---|---|---|
| Portfolio optimisation | Holdings of 0 to 3 units per asset and direction; the capital and budget limits in every period | QOBLIB's official objective: risk minus return, plus transaction, short-selling and liquidation costs, minus interest on cash |
| Network design | Every node has exactly 2 outgoing and 2 incoming links; the flows deliver all the demand and use only chosen links | The largest total flow on any link, in units of 1/1000 |

**Quality** is your gap to the best-known value published on QOBLIB:

    gap = (your score − best known) / |best known|

A gap of 0% matches the best-known value, and a negative gap beats it. For example, −69 169 on
`po_a010_t10_orig` (budget 4, λ = 10⁻⁴; best known −69 482) is a gap of 0.45%. Best-known values are in
QOBLIB's tables for [portfolio optimisation](https://github.com/ZIB-AOPT/QOBLIB/blob/main/06-portfolio/solutions/README.md)
and [network design](https://github.com/ZIB-AOPT/QOBLIB/blob/main/08-network/solutions/README.md), and
each problem notebook lists targets.

**Scale** is the size of the instance you solve (its binary variables) and the qubits of your largest
quantum program.

To check a file before you hand it in:

```python
import qoblib_tools as qt

# Portfolio optimisation
header, positions = qt.read_portfolio_solution("po_a010_t10_orig_b004_l1e-4.sol")
model = qt.PortfolioModel(qt.load_portfolio_instance(header["instance"]),
                          budget=int(header["budget"]), lam=header["lambda"])
print(model.score(positions))  # objective, feasible, breakdown, violations

# Network design (network12 has 12 nodes)
print(qt.check_network_solution("network12.sol", 12, qt.load_network_demand(12)))  # (valid, max_flow, message)
```

## Known limits

* **Saved outputs** come from one run with an API key: circuits on the local simulator, the
  Characterization Service calls (one in each notebook) in Qoro's cloud. Your numbers will differ from
  run to run, and more so with `USE_CLOUD = True`.
* **Run times (one run, 12-core Mac):** 00 about 1 to 4 minutes, 01 about 6 minutes, 02 about 7
  minutes. Most of it is the characterization calls, which took from seconds to 6 minutes each; without
  a key they are skipped and every notebook runs in under 5 minutes. With `USE_CLOUD = True`, 00 took
  5 minutes and 02 took 7 minutes in our runs. Colab is slower.
* **Classical tools do much of the work.** Repair and local search are classical and strong; compare
  every quantum result with the classical baselines in the notebooks before claiming a quantum
  contribution.
* **Cost-landscape scans** (`divi.viz`: `scan_1d`, `scan_2d`, `scan_pca`) work on the portfolio and
  network programs, but the notebooks don't show them.
* The referees are ports of QOBLIB's checkers. Before submitting a result to QOBLIB, also run QOBLIB's own
  checker (`cargo build --release` in the problem's `check/` folder).

## Files in this folder

| File | |
|---|---|
| `README.md` | This file |
| `00_main_qubo_101.ipynb` | Main notebook: setup, QUBO 101, choosing a problem, handing in |
| `01_portfolio_optimisation.ipynb` | Portfolio optimisation (QOBLIB 06) |
| `02_network_design.ipynb` | Network design (QOBLIB 08) |
| `qoblib_tools.py` | Helper and referee for 01 and 02 |
| `LICENSE` | Apache-2.0 |

Created when you run the notebooks (ignored by git): `qoblib_data/` (downloaded instances), the `.sol`
files, `__pycache__/`.
