"""
Formule della relazione come immagini PNG (matplotlib mathtext), leggibili uguali in Word e in PDF.

Uso: python relazione_formule.py <out_dir>
"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
plt.rcParams['mathtext.fontset'] = 'dejavuserif'
F = {
    'f_reticolo': r'$\mathrm{reticolo} = \{\, i : \mathrm{acc}_i > 4000 \,\}\quad\Leftrightarrow\quad A_i > 4000 \cdot 25\ \mathrm{m^2} = 0{,}1\ \mathrm{km^2}$',
    'f_d8': r'$\mathrm{direzione}(i) = \mathrm{arg\,max}_{\,j}\ \frac{z_i - z_j}{d_{ij}},\qquad d_{ij} = 5\ \mathrm{m\ (lato)},\ \ 5\sqrt{2}\ \mathrm{m\ (diagonale)}$',
    'f_area': r'$A = n_{\mathrm{celle}} \cdot \Delta x \cdot \Delta y = n_{\mathrm{celle}} \cdot 25\ \mathrm{m^2}$',
    'f_iou': r'$\mathrm{IoU} = \frac{\mathrm{area}(A \cap B)}{\mathrm{area}(A \cup B)}$',
    'f_cn': r'$CN_{\mathrm{medio}} = \frac{1}{n} \sum_{i\, \in\, \mathrm{bacino}} CN_i$',
    'f_scs': r'$S = \frac{25400}{CN} - 254,\qquad I_a = 0{,}2\,S,\qquad Q = \frac{(P - I_a)^2}{P - I_a + S}\quad (P > I_a)$',
    'f_L': r'$L = \max_{i\, \in\, \mathrm{bacino}}\ \sum_{i \rightarrow \mathrm{sezione}} d_{\mathrm{passo}},\qquad d_{\mathrm{passo}} = 5\ \mathrm{m}\ \mathrm{oppure}\ 5\sqrt{2}\ \mathrm{m}$',
    'f_P': r'$P = n_{\mathrm{lati\ di\ confine}} \cdot 5\ \mathrm{m}$',
    'f_quote': r'$AE = \frac{1}{n}\sum_i z_i,\qquad R = z_{\max} - z_{\min},\qquad HI = \frac{AE - z_{\min}}{R}$',
    'f_s': r'$s_i = \max_{j}\ \max\left(0,\ \frac{z_i - z_j}{d_{ij}}\right),\qquad S = \frac{1}{n}\sum_i s_i$',
    'f_tratto': r'$i_{\mathrm{tratto}} = \frac{z_{\mathrm{monte}} - z_{\mathrm{valle}}}{d_{\mathrm{monte}} + d_{\mathrm{valle}}},\qquad d_{\mathrm{monte}} = d_{\mathrm{valle}} = 250\ \mathrm{m}$',
}
for nome, tex in F.items():
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=15, color='#111111')
    fig.savefig(os.path.join(out, nome + '.png'), dpi=300, bbox_inches='tight', pad_inches=0.06, transparent=False,
                facecolor='white')
    plt.close(fig)
    print(nome)
