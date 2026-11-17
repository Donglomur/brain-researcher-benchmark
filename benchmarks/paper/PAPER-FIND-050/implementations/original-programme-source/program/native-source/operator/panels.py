"""Source-specific deterministic input preparation; never imported by the packager.

No silent repairs: source uint8 spike aggregation, panel-specific cropping,
normalization, and spatial split conventions are retained. The explicit array
ceiling is a planning guard, not an OS RSS guarantee.
"""
from pathlib import Path


def need(ok, message):
    if not ok:
        raise ValueError(message)


def load_panels(data_root, session, array_ceiling_bytes):
    import numpy as np
    from scipy.sparse import csr_matrix
    path = Path(data_root) / session["file"]
    with np.load(path, allow_pickle=False) as data:
        if session["modality"] == "calcium":
            raw = data["sp"]
            need(raw.ndim == 2 and raw.dtype.kind == "f", "Numeric neuron-by-time calcium matrix")
            need(raw.nbytes * 6 <= array_ceiling_bytes, "Conservative calcium preparation array ceiling")
            x, y = data["xpos"], data["ypos"]
            start = data["tstart"].item() if "tstart" in data else 0
            need(type(start) is int and 0 <= start < raw.shape[1], "Source Fig2 tstart integer")
            fig2, fig3 = raw[:, start:].copy(), raw.copy()
        else:
            # Do not load the unused object/string areas member or allow pickle.
            st, clu = data["st"], data["clu"]
            need(st.ndim == clu.ndim == 1 and len(st) == len(clu) > 0 and st.dtype.kind == "f" and clu.dtype.kind in "iu", "Spike event vectors")
            need(np.isfinite(st).all() and clu.min() >= 0, "Finite spike events")
            st = st - st.min()
            ticks = np.round(st / (1.0 / 22))
            need(ticks.max() < 2**32, "Source uint32 timestamp support")
            rows, columns = int(clu.max()) + 1, int(ticks.max()) + 1
            need(rows * columns * 16 + st.nbytes * 6 + clu.nbytes * 4 <= array_ceiling_bytes,
                 "Conservative spike preparation array ceiling before dense allocation")
            sp = csr_matrix((np.ones(clu.size, "uint8"), (clu, ticks.astype("uint32"))),
                            shape=(rows, columns)).toarray().astype("float32")
            good = sp.mean(axis=1) > .01 / 22
            raw = sp[good]
            y, x = data["ypos"][good], data["iprobe"][good].astype("float32") * 0
            fig2, fig3 = raw.copy(), raw.copy()
        need(x.shape == y.shape == (fig3.shape[0],), "Neuron coordinates align")
        need(np.isfinite(x).all() and np.isfinite(y).all() and np.isfinite(fig2).all() and np.isfinite(fig3).all(), "Finite numeric inputs")
    return fig2, fig3, x, y


def split_counts(x, y, spacing):
    ix = (((x % (2 * spacing) < spacing).astype("int32") + (y % (2 * spacing) < spacing).astype("int32")) % 2) == 0
    return int(ix.sum()), int((~ix).sum())


def geometry(session, pin, fig2, fig3, x, y):
    a, b = split_counts(x, y, 40 if session["modality"] == "ephys" else 25)
    c, d = split_counts(x, y, 25)
    return {"session_id": session["session_id"], "input_sha256": pin,
            "n_fig2": int(fig2.shape[0]), "t_fig2": int(fig2.shape[1]), "ntrain_fig2": a, "ntest_fig2": b,
            "n_fig3": int(fig3.shape[0]), "t_fig3": int(fig3.shape[1]), "ntrain_fig3": c, "ntest_fig3": d,
            "dmd_modes": min(1000, int(fig3.shape[0]))}
