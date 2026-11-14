from vidcut.editor.timeline import Clip, TimelineModel


def _model(duration: float = 20.0) -> TimelineModel:
    m = TimelineModel()
    m.load("/videos/a.mp4", duration, True, 2, 48000)
    return m


def _spans(m: TimelineModel):
    return [(round(c.start, 6), round(c.end, 6)) for c in m.clips]


def test_load_creates_one_clip():
    m = _model(20.0)
    assert _spans(m) == [(0.0, 20.0)]
    assert m.total == 20.0


def test_split_and_refuse_too_short_cuts():
    m = _model()
    assert m.split(5.0) and m.split(12.0)
    assert _spans(m) == [(0.0, 5.0), (5.0, 12.0), (12.0, 20.0)]
    assert not m.split(5.01)  # too close to an existing cut
    assert not m.split(0.0)  # on the very start


def test_delete_ripples_later_clips_forward():
    m = _model()
    m.split(5.0)
    m.split(12.0)
    assert m.delete(1)
    assert _spans(m) == [(0.0, 5.0), (12.0, 20.0)]
    assert m.total == 13.0
    assert m.locate(6.0) == (1, 13.0)


def test_undo_and_redo_restore_state():
    m = _model()
    m.split(5.0)
    m.split(12.0)
    m.delete(1)
    assert m.undo() and m.total == 20.0 and len(m.clips) == 3
    assert m.redo() and m.total == 13.0


def test_new_edit_clears_redo():
    m = _model()
    m.split(5.0)
    m.undo()
    m.split(2.0)
    assert not m.can_redo()


def test_delete_last_clip_leaves_empty_timeline():
    m = _model(10.0)
    assert m.delete(0)
    assert m.clips == () and m.total == 0 and m.index_at(0.0) is None


def test_export_merges_clips_that_continue_each_other():
    m = _model()
    m.split(5.0)
    m.split(10.0)
    assert _spans(m) and m.export_clips() == [Clip(0.0, 20.0)]
    m.delete(1)
    assert [(c.start, c.end) for c in m.export_clips()] == [(0.0, 5.0), (10.0, 20.0)]


def test_boundaries_follow_the_timeline():
    m = _model()
    m.split(4.0)
    m.delete(0)
    assert m.boundaries() == [0.0, 16.0]
