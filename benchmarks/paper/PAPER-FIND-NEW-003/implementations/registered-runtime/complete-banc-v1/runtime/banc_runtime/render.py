"""Deterministic complete-support audit figures, separate from paper aesthetics."""
from html import escape
from .codec import need, finite_number, encode, pin


def heatmap_svg(values, rows, columns, *, low, high, title, meter):
    """Real SVG producer; missing cells stay visibly distinct.

    This figure is for inspecting a completed matrix. Original palette,
    clustering, anatomy and publication panel parity remain in native R and
    G13/G16. Nothing in this function awards paper reconstruction credit.
    """
    need(type(rows) is tuple and type(columns) is tuple and rows and columns,
         'explicit complete ordered display support')
    need(len(rows)==len(set(rows)) and len(columns)==len(set(columns)), 'unique labels')
    need(len(values)==len(rows) and all(len(x)==len(columns) for x in values), 'complete matrix')
    need(finite_number(low) and finite_number(high) and low<high, 'explicit finite scale')
    need(all(v is None or finite_number(v) for line in values for v in line), 'finite cells or absent')
    meter.admit_pairs(len(rows)*len(columns))
    w,h=200+30*len(columns),150+26*len(rows)
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<g font-family="sans-serif" font-size="10">',
           '<text x="10" y="16">'+escape(title)+'</text>',
           '<text x="10" y="31">Audit support only; grey = absent; no native plot parity claim</text>']
    for j,label in enumerate(columns):
        parts.append(f'<text transform="translate({185+30*j},130) rotate(-55)">'+escape(label)+'</text>')
    for i,label in enumerate(rows):
        y=145+26*i
        parts.append(f'<text x="5" y="{y+17}">'+escape(label)+'</text>')
        for j,v in enumerate(values[i]):
            fraction=None if v is None else min(1,max(0,(v-low)/(high-low)))
            color='#bdbdbd' if fraction is None else '#%02x%02x%02x'%(round(240-190*fraction),round(248-140*fraction),round(255-70*fraction))
            parts.append(f'<rect x="{180+30*j}" y="{y}" width="29" height="25" fill="{color}"><title>'+escape(str(v))+'</title></rect>')
    parts.append('</g></svg>')
    raw=('\n'.join(parts)+'\n').encode()
    meter.reserve_output(len(raw));meter.complete_output(len(raw))
    return {'svg':raw,'identity':pin(raw),'support_sha256':pin(encode({'rows':rows,'columns':columns,'values':values}))['sha256'],
            'publication_plot_parity':False}
