"""
Controlli automatici dei parametri morfometrici (bacini_5m_parametri.csv).

1. Coerenza interna (algebra e limiti fisici):
   - area da celle = area del poligono del bacino (entro 2%);
   - L >= Lb (il percorso di flusso non puo' essere piu' corto della retta);
     sinuosita' L/Lb tra 1 e 3;
   - Kc >= 1, Rc <= 1, Rc = 1/Kc^2; Re = 2*sqrt(FF/pi); HI tra 0 e 1;
   - quota min <= quota media <= quota max; rilievo = max - min;
   - Melton = (R/1000)/sqrt(A); CN tra 25 e 100 (se presente).
2. Leggi empiriche: legge di Hack L = c*A^h stimata sui bacini stessi;
   segnalati i bacini fuori di un fattore 2.
3. Coerenza tra bacini annidati (ponte a monte nel bacino di un ponte a valle):
   A, L, quota max devono crescere verso valle, quota min decrescere.

Uso: python verifica_parametri.py <bacini_5m_parametri.csv> <risultati_5m.gpkg> <out.xlsx>
"""
import sys

import numpy as np
import pandas as pd
import geopandas as gpd

par, gpkg, out = sys.argv[1:4]
P = pd.read_csv(par).set_index('ID')
B = gpd.read_file(gpkg, layer='bacini').set_index('ID')
S = gpd.read_file(gpkg, layer='sezioni_chiusura').set_index('ID')
C = pd.DataFrame(index=P.index)
C['A_poligono_km2'] = B.geometry.area.reindex(P.index) / 1e6
C['Err_area_celle_vs_poligono'] = (P.A_km2 / C.A_poligono_km2 - 1)
C['OK_area_poligono'] = C.Err_area_celle_vs_poligono.abs() <= 0.02
C['Sinuosita_L_su_Lb'] = P.L_km / P.Lb_km
C['OK_L_maggiore_Lb'] = P.L_km >= P.Lb_km * 0.999
C['OK_sinuosita_1_3'] = C.Sinuosita_L_su_Lb.between(1, 3)
C['OK_Kc_maggiore_1'] = P.Compattezza_Kc >= 1
C['OK_Rc_minore_1'] = P.Circolarita_Rc <= 1
C['OK_Rc_uguale_1_su_Kc2'] = np.isclose(P.Circolarita_Rc, 1 / P.Compattezza_Kc ** 2, rtol=1e-6)
C['OK_Re_da_FF'] = np.isclose(P.Elongazione_Re, 2 * np.sqrt(P.FF / np.pi), rtol=1e-6)
C['OK_HI_0_1'] = P.Integrale_ipsometrico.between(0, 1)
C['OK_quote'] = (P.Quota_min_m <= P.AE_m) & (P.AE_m <= P.Quota_max_m) & \
    np.isclose(P.Rilievo_m, P.Quota_max_m - P.Quota_min_m)
C['OK_Melton'] = np.isclose(P.Melton, (P.Rilievo_m / 1000) / np.sqrt(P.A_km2), rtol=1e-6)
C['OK_CN_25_100'] = P.CN_medio.between(25, 100) | P.CN_medio.isna()
C['Quota_area_con_CN'] = P.Quota_area_con_CN
# legge di Hack
lg = np.polyfit(np.log(P.A_km2), np.log(P.L_km), 1)
C['L_Hack_km'] = np.exp(lg[1]) * P.A_km2 ** lg[0]
C['Rapporto_L_su_Hack'] = P.L_km / C.L_Hack_km
C['OK_Hack_fattore_2'] = C.Rapporto_L_su_Hack.between(0.5, 2)
# annidamento
coppie, viol = [], {}
si = S.sindex
for b, poly in B.geometry.items():
    for a in S.index[list(si.query(poly, predicate='intersects'))]:
        if a == b or P.A_km2[a] >= P.A_km2[b]:
            continue
        v = []
        if P.L_km[a] > P.L_km[b] * 1.001:
            v.append('L monte > L valle')
        if P.Quota_max_m[a] > P.Quota_max_m[b] + 1:
            v.append('quota max monte > valle')
        if P.Quota_min_m[a] < P.Quota_min_m[b] - 1:
            v.append('quota min monte < valle')
        coppie.append({'ID_monte': a, 'ID_valle': b, 'A_monte': P.A_km2[a], 'A_valle': P.A_km2[b],
                       'L_monte': P.L_km[a], 'L_valle': P.L_km[b], 'Incoerenze': '; '.join(v)})
        for x in (a, b):
            if v:
                viol.setdefault(x, []).append(f'{a}->{b}: ' + ', '.join(v))
C['Incoerenze_annidamento'] = pd.Series({k: ' | '.join(v) for k, v in viol.items()})
C['OK_annidamento'] = C.Incoerenze_annidamento.isna()
ok_cols = [c for c in C.columns if c.startswith('OK_')]
C['N_controlli_falliti'] = (~C[ok_cols].fillna(True).astype(bool)).sum(axis=1)
sint = pd.DataFrame({'Controllo': ok_cols,
                     'Superati': [int(C[c].fillna(True).astype(bool).sum()) for c in ok_cols],
                     'Falliti': [int((~C[c].fillna(True).astype(bool)).sum()) for c in ok_cols],
                     'ID falliti': [', '.join(map(str, C.index[~C[c].fillna(True).astype(bool)])) for c in ok_cols]})
sint.loc[len(sint)] = ['Legge di Hack stimata', '', '', f'L = {np.exp(lg[1]):.2f} · A^{lg[0]:.2f} (km, km²)']
with pd.ExcelWriter(out, engine='openpyxl') as w:
    sint.to_excel(w, sheet_name='Sintesi controlli', index=False)
    C.reset_index().to_excel(w, sheet_name='Controlli per ponte', index=False)
    pd.DataFrame(coppie).to_excel(w, sheet_name='Bacini annidati', index=False)
    for ws in w.book.worksheets:
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                max(len(str(c.value)) if c.value is not None else 0 for c in col) + 2, 60)
        ws.freeze_panes = 'B2'
print(sint.to_string(index=False))
