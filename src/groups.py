"""Fase 2 — grupos de municípios (PLANO.md, seções 1, 1A e 5).

Esquemas presidenciais (base 2010 → final 2026, config.yaml):
1. Swing relativo: swing_m = (s_m,f − s_m,b) − (s_BR,f − s_BR,b), s = % do PT nos válidos.
   s_BR é o share nacional sem exterior/trânsito (mesma base dos municípios).
   Grupos centrados em zero (zero = acompanhou a maré nacional), com DP não ponderado dos swings:
   g_swing    : ±1 DP (principal)       g_swing_dp05: ±0,5 DP
   g_swing_q5 : quintis (Q5 = G_PT, Q1 = G_OP, Q2–Q4 = G_EST)
   g_swing_t3 : tercis
2. Tipologia 2×2 sobre aptos: sinais de Δe_PT e Δe_OP (b → f). Δ = 0 conta como "↑".
   tipo_2x2 (variação bruta, principal) e tipo_2x2_rel (variação menos a variação nacional).
3. Clusters de trajetória: k-means sobre d_m,t = s_m,t − s_BR,t para t = 2010…2026. Os desvios em
   relação ao share nacional tiram a maré e deixam todos os anos na mesma escala (p.p.), sem
   z-score por ano, que apagaria a mudança de dispersão entre eleições. Dois modos:
   - 'nivel': d_m,t como está. Os clusters separam sobretudo o nível do voto PT.
   - 'forma': d_m,t − média_t(d_m,t), a série centrada na média de cada município. Os clusters
     separam o formato da trajetória (subida, queda, pico em 2018 …), independente do nível.
   k = 3–6, escolha por silhueta dentro de cada modo; todos os k ficam salvos em
   `cluster_{modo}_k{k}`. `cluster_nivel` e `cluster_forma` = k de config.yaml (grupos.k_escolhido;
   se ausente, o de maior silhueta), com rótulos interpretativos em `cluster_{modo}_rotulo`.

Esquemas proporcionais (por eleição e versão):
4. g_prop: P_PT / P_ANTI / P_OUTRO pelo partido mais votado (empates no 1º lugar = NA).
   g_prop_margem: mais votado com margem ≥ 5 p.p. (P_PT / P_ANTI), senão P_NENHUM.
   destaque_p80_PT / destaque_p80_ANTI: p ≥ percentil 80 da distribuição municipal do partido no ano
   (não exclusivos entre si; flags separadas).
5. Trajetória proporcional (versão partido, 6 eleições): enraizado_PT (PT lidera em ≥ 4),
   enraizado_ANTI (antipetista do ano lidera em ≥ 4), migrante_PT_ANTI (PT liderou em 2006–2014,
   o antipetista lidera em 2022 ou 2026 e o PT não lidera em nenhuma das duas), migrante_ANTI_PT
   (o inverso), nunca_polarizado (nenhum dos dois lidera em nenhuma), intermitente (o resto).

Saídas:
- data/processed/grupos_presidenciais.parquet (id_amc)
- data/processed/grupos_proporcionais.parquet (id_amc × ano × versão)
- outputs/tables/fase2_*.csv e .md
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

from src.utils import caminho, config

log = logging.getLogger("groups")
ORDEM_G = ["G_PT", "G_EST", "G_OP"]
ORDEM_P = ["P_PT", "P_ANTI", "P_OUTRO"]


def carregar() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pres = pd.read_parquet(caminho("interim") / "tse_presidencial.parquet")
    prop = pd.read_parquet(caminho("interim") / "tse_proporcional.parquet")
    malha = pd.read_parquet(caminho("interim") / "malha_amc.parquet", columns=["id_amc", "regiao"])
    return pres, prop, malha


def share_nacional(pres: pd.DataFrame) -> pd.Series:
    g = pres.groupby("ano")[["votos_pt", "validos"]].sum()
    return 100 * g["votos_pt"] / g["validos"]


def _por_limiar(x: pd.Series, lim: float) -> pd.Series:
    return pd.Series(np.select([x >= lim, x <= -lim], ["G_PT", "G_OP"], "G_EST"), index=x.index)


def _por_quantil(x: pd.Series, q: int) -> pd.Series:
    r = pd.qcut(x, q, labels=False)
    return pd.Series(np.select([r == q - 1, r == 0], ["G_PT", "G_OP"], "G_EST"), index=x.index)


def grupos_swing(pres: pd.DataFrame, base: int, final: int) -> pd.DataFrame:
    s = pres.pivot(index="id_amc", columns="ano", values="s_pt")
    br = share_nacional(pres)
    out = pd.DataFrame(index=s.index)
    out["swing"] = (s[final] - s[base]) - (br[final] - br[base])
    dp = out["swing"].std()
    out["g_swing"] = _por_limiar(out["swing"], config()["grupos"]["limiar_dp"] * dp)
    out["g_swing_dp05"] = _por_limiar(out["swing"], 0.5 * dp)
    out["g_swing_q5"] = _por_quantil(out["swing"], 5)
    out["g_swing_t3"] = _por_quantil(out["swing"], 3)
    log.info("swing %d→%d: média %.2f, DP %.2f p.p.", base, final, out["swing"].mean(), dp)
    return out


def tipologia_2x2(pres: pd.DataFrame, base: int, final: int) -> pd.DataFrame:
    e = pres.pivot(index="id_amc", columns="ano", values=["e_pt", "e_op"])
    g = pres.groupby("ano")[["votos_pt", "votos_op", "aptos"]].sum()
    br_pt, br_op = 100 * g["votos_pt"] / g["aptos"], 100 * g["votos_op"] / g["aptos"]
    out = pd.DataFrame(index=e.index)
    out["d_e_pt"] = e[("e_pt", final)] - e[("e_pt", base)]
    out["d_e_op"] = e[("e_op", final)] - e[("e_op", base)]

    def rotular(dpt, dop):
        return pd.Series(np.select(
            [(dpt >= 0) & (dop < 0), (dpt < 0) & (dop >= 0), (dpt >= 0) & (dop >= 0)],
            ["PT↑OP↓", "PT↓OP↑", "ambos↑"], "ambos↓"), index=dpt.index)

    out["tipo_2x2"] = rotular(out["d_e_pt"], out["d_e_op"])
    out["tipo_2x2_rel"] = rotular(out["d_e_pt"] - (br_pt[final] - br_pt[base]),
                                  out["d_e_op"] - (br_op[final] - br_op[base]))
    return out


def clusters_trajetoria(pres: pd.DataFrame, anos: list[int]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    s = pres.pivot(index="id_amc", columns="ano", values="s_pt")[anos]
    D = s - share_nacional(pres)[anos]
    out, centros, silh = pd.DataFrame(index=D.index), [], {}
    for modo, X in [("nivel", D), ("forma", D.sub(D.mean(axis=1), axis=0))]:
        for k in config()["grupos"]["k_clusters"]:
            km = KMeans(n_clusters=k, n_init=50, random_state=0).fit(X.values)
            # ordem dos rótulos: nível → desvio médio (C1 = mais petista); forma → variação final − inicial
            cc = km.cluster_centers_
            chave = cc.mean(axis=1) if modo == "nivel" else cc[:, -1] - cc[:, 0]
            ordem = np.argsort(-chave)
            renum = {old: new + 1 for new, old in enumerate(ordem)}
            col = f"cluster_{modo}_k{k}"
            out[col] = pd.Series(km.labels_, index=X.index).map(renum)
            silh[(modo, k)] = silhouette_score(X.values, km.labels_)
            # centróide reportado sempre em desvios d_m,t (média dos membros), para interpretação
            c = D.groupby(out[col]).mean().reset_index().rename(columns={col: "cluster"})
            c.insert(0, "k", k)
            c.insert(0, "modo", modo)
            c["n"] = out[col].value_counts().sort_index().values
            centros.append(c)
        k_silh = max((k for m, k in silh if m == modo), key=lambda k: silh[(modo, k)])
        k_best = (config()["grupos"].get("k_escolhido") or {}).get(modo) or k_silh
        out[f"cluster_{modo}"] = out[f"cluster_{modo}_k{k_best}"]
        rot = (config()["grupos"].get("rotulos_cluster") or {}).get(modo, {})
        out[f"cluster_{modo}_rotulo"] = out[f"cluster_{modo}"].map(lambda c: f"{c}: {rot.get(c, '')}".rstrip(": "))
        log.info("silhueta %s: %s → melhor silhueta k = %d; k usado = %d", modo,
                 {k: round(v, 3) for (m, k), v in silh.items() if m == modo}, k_silh, k_best)
    return out, pd.concat(centros, ignore_index=True), silh


def grupos_proporcionais(prop: pd.DataFrame) -> pd.DataFrame:
    df = prop[["ano", "versao", "id_amc", "lider", "empate_lider", "unidade_PT", "unidade_ANTI",
               "p_PT", "p_ANTI", "margem_PT", "margem_ANTI", "nep"]].copy()
    lim = config()["grupos"]["limiar_margem_pp"]
    g = np.select([df["lider"] == df["unidade_PT"], df["lider"] == df["unidade_ANTI"]], ["P_PT", "P_ANTI"], "P_OUTRO")
    df["g_prop"] = pd.Series(g, index=df.index).where(~df["empate_lider"])
    gm = np.select([(df["lider"] == df["unidade_PT"]) & (df["margem_PT"] >= lim),
                    (df["lider"] == df["unidade_ANTI"]) & (df["margem_ANTI"] >= lim)], ["P_PT", "P_ANTI"], "P_NENHUM")
    df["g_prop_margem"] = pd.Series(gm, index=df.index).where(~df["empate_lider"])
    pct = config()["grupos"]["percentil_destaque"] / 100
    for p in ["PT", "ANTI"]:
        corte = df.groupby(["ano", "versao"])[f"p_{p}"].transform(lambda x: x.quantile(pct))
        df[f"destaque_p80_{p}"] = df[f"p_{p}"] >= corte
    return df


def trajetoria_proporcional(gp: pd.DataFrame) -> pd.DataFrame:
    w = gp[gp["versao"] == "partido"].pivot(index="id_amc", columns="ano", values="g_prop")
    anos = list(w.columns)
    ini = [a for a in anos if a <= 2014]
    fim = [a for a in anos if a >= 2022]
    lid_pt, lid_anti = (w == "P_PT"), (w == "P_ANTI")
    out = pd.DataFrame(index=w.index)
    out["n_lid_PT"], out["n_lid_ANTI"] = lid_pt.sum(axis=1), lid_anti.sum(axis=1)
    out["traj_prop"] = np.select(
        [out["n_lid_PT"] >= 4, out["n_lid_ANTI"] >= 4,
         lid_pt[ini].any(axis=1) & lid_anti[fim].any(axis=1) & ~lid_pt[fim].any(axis=1),
         lid_anti[ini].any(axis=1) & lid_pt[fim].any(axis=1) & ~lid_anti[fim].any(axis=1),
         (out["n_lid_PT"] == 0) & (out["n_lid_ANTI"] == 0)],
        ["enraizado_PT", "enraizado_ANTI", "migrante_PT_ANTI", "migrante_ANTI_PT", "nunca_polarizado"],
        "intermitente")
    return out


def _cramer_v(a: pd.Series, b: pd.Series) -> float:
    t = pd.crosstab(a, b).values
    n = t.sum()
    esp = t.sum(1, keepdims=True) * t.sum(0, keepdims=True) / n
    chi2 = ((t - esp) ** 2 / esp).sum()
    return float(np.sqrt(chi2 / (n * (min(t.shape) - 1))))


def _salvar(df: pd.DataFrame, nome: str, index: bool = True) -> None:
    df.to_csv(caminho("tables") / f"{nome}.csv", index=index, encoding="utf-8")
    (caminho("tables") / f"{nome}.md").write_text(df.to_markdown(index=index, floatfmt=".2f"), encoding="utf-8")


def tabelas(gpres: pd.DataFrame, gprop: pd.DataFrame, centros: pd.DataFrame, silh: dict, base: int, final: int) -> None:
    # tamanho dos grupos
    linhas = []
    for col in ["g_swing", "g_swing_dp05", "g_swing_q5", "g_swing_t3", "tipo_2x2", "tipo_2x2_rel",
                "cluster_nivel", "cluster_forma", "traj_prop"]:
        vc = gpres[col].value_counts().sort_index()
        apt = gpres.groupby(col)[f"aptos_{final}"].sum() / gpres[f"aptos_{final}"].sum() * 100
        linhas += [{"esquema": col, "grupo": str(k), "n_amc": int(v), "pct_eleitorado": apt[k]} for k, v in vc.items()]
    _salvar(pd.DataFrame(linhas), "fase2_tamanho_grupos", index=False)

    # silhueta e centróides
    _salvar(pd.DataFrame([{"modo": m, "k": k, "silhueta": v} for (m, k), v in silh.items()]),
            "fase2_silhueta", index=False)
    _salvar(centros, "fase2_centroides_clusters", index=False)

    # concordância entre esquemas presidenciais
    esquemas = ["g_swing", "g_swing_q5", "tipo_2x2", "tipo_2x2_rel", "cluster_nivel", "cluster_forma"]
    conc = pd.DataFrame(index=esquemas, columns=esquemas, dtype=float)
    ari = conc.copy()
    for a in esquemas:
        for b in esquemas:
            conc.loc[a, b] = _cramer_v(gpres[a], gpres[b])
            ari.loc[a, b] = adjusted_rand_score(gpres[a], gpres[b])
    _salvar(conc, "fase2_concordancia_cramer_v")
    _salvar(ari, "fase2_concordancia_ari")
    for a, b in [("g_swing", "tipo_2x2"), ("g_swing", "cluster_nivel"), ("g_swing", "cluster_forma"),
                 ("cluster_nivel", "cluster_forma"), ("g_swing", "traj_prop")]:
        _salvar(pd.crosstab(gpres[a], gpres[b], margins=True), f"fase2_cruzamento_{a}_x_{b}")

    # matriz presidencial × proporcional (versão partido) em base e final
    gp = gprop[gprop["versao"] == "partido"]
    for ano in [base, final]:
        m = gpres[["g_swing"]].join(gp[gp["ano"] == ano].set_index("id_amc")["g_prop"])
        t = pd.crosstab(m["g_swing"], m["g_prop"], margins=True).reindex(ORDEM_G + ["All"])[ORDEM_P + ["All"]]
        _salvar(t, f"fase2_matriz_pres_x_prop_{ano}")
        pct = pd.crosstab(m["g_swing"], m["g_prop"], normalize="index").reindex(ORDEM_G)[ORDEM_P] * 100
        _salvar(pct, f"fase2_matriz_pres_x_prop_{ano}_pct_linha")

    # grupos proporcionais por eleição
    resumo = (gprop.groupby(["versao", "ano"])["g_prop"].value_counts().unstack().fillna(0).astype(int))
    _salvar(resumo, "fase2_grupos_proporcionais_por_eleicao")
    resumo_m = (gprop.groupby(["versao", "ano"])["g_prop_margem"].value_counts().unstack().fillna(0).astype(int))
    _salvar(resumo_m, "fase2_grupos_proporcionais_margem_por_eleicao")


def main() -> None:
    cfg = config()
    base, final = cfg["ano_base"], cfg["ano_final"]
    pres, prop, malha = carregar()
    anos_traj = [a for a in cfg["anos_eleicao"] if a >= base]
    sw = grupos_swing(pres, base, final)
    tp = tipologia_2x2(pres, base, final)
    cl, centros, silh = clusters_trajetoria(pres, anos_traj)
    gprop = grupos_proporcionais(prop)
    trp = trajetoria_proporcional(gprop)
    aptos = pres.pivot(index="id_amc", columns="ano", values="aptos").add_prefix("aptos_")
    uf = pres.drop_duplicates("id_amc").set_index("id_amc")["sg_uf"]
    gpres = (sw.join(tp).join(cl).join(trp).join(aptos).join(uf).join(malha.set_index("id_amc")["regiao"])
             .reset_index())
    gpres.to_parquet(caminho("processed") / "grupos_presidenciais.parquet", index=False)
    gprop.to_parquet(caminho("processed") / "grupos_proporcionais.parquet", index=False)
    tabelas(gpres.set_index("id_amc"), gprop, centros, silh, base, final)
    log.info("grupos salvos: %d AMCs", len(gpres))


if __name__ == "__main__":
    main()
