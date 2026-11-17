"""All six scientific figure consumers, with actual observed time coordinates."""
from .core import Refusal, Custody
from .roster import FIGURES
from .transitions import TRANSITIONS
from .statistics import planned_family_names


def figure_plan(group):
    names = planned_family_names()
    return {
        'figure1': tuple('transition_' + c for c in TRANSITIONS) + ('method_reordering',) + tuple(
            n for n in names if '/sound/' in n and 'most_likely' not in n),
        'figure2': ('method_prediction',) + tuple(n for n in names if 'most_likely' in n),
        'supplement1': ('accuracy/sound/replication/random',),
        'supplement2': tuple(n for n in names if '/omission/' in n),
        'supplement3': ('fisher_difference/sound/empirical', 'fisher_difference/sound/theoretical',
                        'fisher_difference/sound/most_likely_empirical'),
        'supplement4': ('transition_midplus', 'OOF_confusion_at_210ms'),
    }



def draw(group, *, operation, custody):
    import numpy as np
    import matplotlib.pyplot as plt
    train, test = group.axes
    plan = figure_plan(group)
    if set(plan) != set(FIGURES) or any(not rows for rows in plan.values()):
        raise Refusal('complete six-figure family required')
    figures = {}
    local = Custody(custody)
    try:
        operation = operation.scoped(local)
        for name, panels in plan.items():
            with operation('figure', {'name': name, 'panels': len(panels)}):
                figure, axs = plt.subplots(len(panels), 1, figsize=(9, max(3, 2.7*len(panels))), squeeze=False)
                figures[name] = figure
                for ax, panel in zip(axs[:, 0], panels):
                    if panel in group.unavailable:
                        ax.text(.5, .5, 'UNAVAILABLE: ' + group.unavailable[panel]['reason'], ha='center', wrap=True)
                        ax.set_title(panel); ax.set_axis_off(); continue
                    if panel in group.structural:
                        ax.text(.5, .5, 'STRUCTURAL IDENTITY CONTROL: identical random input/support/fit; '
                                'no inferential test or evidence for a scientific null', ha='center', wrap=True)
                        ax.set_title(panel); ax.set_axis_off(); continue
                    if panel.startswith('method_'):
                        text = ('First unused same-label random segment → original-sample map → target sequence; 33 samples per segment, full physical-support purging' if panel == 'method_reordering' else 'Same fitted classifier predictions; score against argmax T[previous retained class, :] instead of actual class. First retained label convention remains explicit.')
                        ax.text(.5,.5,text,ha='center',wrap=True);ax.set_title(panel);ax.set_axis_off();continue
                    if panel.startswith('transition_') or name == 'supplement4':
                        if panel.startswith('transition_'):
                            matrix = np.asarray(TRANSITIONS[panel.removeprefix('transition_')])
                        else:
                            i, j = np.flatnonzero(np.isclose(train, .21)), np.flatnonzero(np.isclose(test, .21))
                            if len(i) != 1 or len(j) != 1:
                                raise Refusal('actual 210ms confusion coordinate unavailable')
                            matrix = group.confusion[i[0], j[0]]
                        image = ax.imshow(matrix, origin='upper', vmin=0, vmax=1)
                        ax.set(xlabel='next/predicted class', ylabel='previous/true class')
                    elif name == 'supplement1':
                        # Actual equal-time join, not a diagonal through unmatched origins.
                        pairs = [(i, int(js[0])) for i, t in enumerate(train)
                                 if len(js := np.flatnonzero(np.isclose(test, t, atol=1e-12, rtol=0))) == 1]
                        if not pairs:
                            raise Refusal('no observed equal-time diagonal')
                        values = group.family[panel][:, [i for i, _ in pairs], [j for _, j in pairs]]
                        times = train[[i for i, _ in pairs]]
                        mean = values.mean(axis=0) + .25
                        sem = values.std(axis=0, ddof=1) / np.sqrt(33)
                        ax.plot(times, mean); ax.fill_between(times, mean-sem, mean+sem, alpha=.25)
                        ax.axhline(.25, color='grey', linestyle='--')
                        ax.set(xlabel='observed train = test time (s)', ylabel='accuracy', xlim=(-.3,.7))
                        ax.set_title(panel); continue
                    else:
                        matrix = np.log10(group.bayes[panel]) if name == 'supplement3' else group.family[panel].mean(axis=0)
                        if panel.startswith('fisher/'):
                            matrix = np.tanh(matrix)
                        image = ax.pcolormesh(test, train, matrix, shading='nearest', cmap='RdBu_r')
                        if panel in group.clusters:
                            result = group.clusters[panel]
                            mask = np.zeros(matrix.shape, dtype=bool)
                            for cluster, p in zip(result['clusters'], result['p']):
                                if p < .05:
                                    mask |= cluster
                            if mask.any() and not mask.all():
                                ax.contour(test, train, mask, levels=[.5], colors='black', linewidths=.5)
                        ax.set(xlabel='observed test time (s)', ylabel='observed train time (s)')
                    ax.set_title(panel)
                    figure.colorbar(image, ax=ax)
                figure.suptitle('corrected_methods_v1 — prospective; not paper reproduction')
                figure.tight_layout()
        return figures
    except BaseException as error:
        if local.first is None:
            local.catch('figure construction', error)
        for figure in figures.values():
            local.close('partial figure retirement', lambda figure=figure: plt.close(figure))
        local.raise_first()
