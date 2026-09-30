"""Character-only adapter; upstream pet engine remains unchanged."""
from copy import copy
import logging
import random
import threading
from PySide6.QtCore import QTimer, Qt, Signal, QPoint
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel
from pet.window import PetWindow
from nyanko_codex_link import EventFeed, TurnState, quota_text, read_quota
from nyanko_choreography import (
    Choreography, IDLE, CLICK, NAP, SNACK, LEFT, RIGHT, WALKS,
    ROUTINES, ALL_CLIPS, PUBLIC, PROTEST, LECTURE, DRAG, DRAG_ENTER, RELEASE,
    RUN_LEFT, RUN_RIGHT, RUNS, MOVES, RUN_DIRECTION, ALERT, CUP, SQUID, SHRIMP, JUMP,
    GUARD, STRETCH, POUNCE,
)

log = logging.getLogger(__name__)

CODEX_DISPLAY_DEFAULTS = {
    'enabled': True,
    'show_activity': True,
    'show_completion': True,
    'show_interrupt': True,
    'show_quota': True,
    'quota_persistent': True,
    'quota_duration_seconds': 15,
}


class NyankoWindow(PetWindow):
    _codex_quota_ready = Signal(int, int, str, bool)

    def __init__(self, lib, config, *args, **kwargs):
        self.choreography = None
        self.routine_history = []
        self._calm_cycles = 0
        self._previous_routine = None
        self._daily_phase = 0
        self._click_counter = 0
        self._nyanko_releasing = False
        self._release_progress = 1.0
        super().__init__(lib, config, *args, **kwargs)
        if lib.character_id != 'nyanko-sensei':
            return
        missing = ALL_CLIPS - set(lib.names())
        if missing:
            log.error('Nyanko routine assets missing: %s', sorted(missing))
            return
        self.choreography = Choreography()
        self._manual_walk = None
        self._manual_walk_timer = QTimer(self)
        self._manual_walk_timer.setSingleShot(True)
        self._manual_walk_timer.timeout.connect(self._dispatch_manual_walk)
        self.idle = IDLE
        self.idles = [IDLE]
        self.clicks = [CLICK, PROTEST]
        self.acts = [NAP, SNACK, LECTURE, ALERT, CUP, SQUID, SHRIMP, JUMP,
                     GUARD, STRETCH, POUNCE]
        self.turns = []
        self.moves = list(MOVES)
        self.drag = DRAG
        self._landing_timer = QTimer(self)
        self._landing_timer.setInterval(30)
        self._landing_timer.timeout.connect(self._finish_throw_feedback)
        self._previous_routine = random.choice([NAP, SNACK])
        self._idle_target = random.randint(4, 7)
        self._switch(IDLE)
        self._setup_codex_link()

    def _setup_codex_link(self):
        """Watch minimal Codex lifecycle events without changing pet animation."""
        self._codex_feed = EventFeed()
        self._codex_state = TurnState()
        self._codex_generation = 0
        self._codex_poll_count = 0
        self._codex_visibility_override = False
        self._codex_revealed_from_fullscreen = False
        self._codex_previous_position = None
        self._codex_reveal_position = None
        self._codex_last_quota = None
        self._codex_chip_mode = None
        self._codex_quota_request_id = 0
        self._codex_applied_settings = self._codex_display_settings()
        log.info('Codex link initialized: %s offset=%d', self._codex_feed.path,
                 self._codex_feed.offset)
        self._codex_chip = QLabel(self)
        self._codex_chip.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self._codex_chip.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._codex_chip.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._codex_chip.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._codex_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._codex_chip.setStyleSheet(
            'QLabel { color: #f7f7f7; background-color: rgba(43, 49, 61, 225); '
            'border: 1px solid rgba(255, 255, 255, 75); border-radius: 9px; '
            'padding: 7px 12px; font-size: 11px; }'
        )
        self._codex_chip.hide()
        self._codex_quota_ready.connect(self._on_codex_quota_ready)
        self._codex_timer = QTimer(self)
        self._codex_timer.setInterval(400)
        self._codex_timer.timeout.connect(self._poll_codex_events)
        self._codex_timer.start()

    def _codex_display_settings(self):
        raw = self.cfg.get('codex_display', {})
        settings = dict(CODEX_DISPLAY_DEFAULTS)
        if isinstance(raw, dict):
            settings.update(raw)
        return settings

    def _set_codex_display_setting(self, key, value):
        settings = self._codex_display_settings()
        settings[key] = value
        self.cfg.set('codex_display', settings)
        self.cfg.save()
        self._codex_applied_settings = settings
        self._apply_codex_display_settings()

    def _extend_context_menu(self, menu):
        if getattr(getattr(self, 'lib', None), 'character_id', None) != 'nyanko-sensei':
            return
        from pet.context_menus.shared import add_action, add_submenu

        for action in tuple(menu.actions()):
            if action.text().strip() == '厉害了我的鲸':
                menu.removeAction(action)

        settings = self._codex_display_settings()
        submenu = add_submenu(menu, 'Codex 联动', 'settings')
        submenu_action = submenu.menuAction()
        menu.removeAction(submenu_action)
        first_action = menu.actions()[0] if menu.actions() else None
        if first_action is None:
            menu.addMenu(submenu)
        else:
            menu.insertMenu(first_action, submenu)
        submenu.setObjectName('nyanko-codex-display-menu')

        link_toggle = submenu.addAction('启用联动提示')
        link_toggle.setCheckable(True)
        link_toggle.setChecked(bool(settings.get('enabled', True)))
        link_toggle.toggled.connect(
            lambda checked: self._set_codex_display_setting('enabled', checked))
        submenu.addSeparator()

        island_cfg = self.cfg.get('dynamic_island', {})
        if not isinstance(island_cfg, dict):
            island_cfg = {}
        island_action = menu.addAction('显示灵动岛')
        island_action.setCheckable(True)
        island_action.setChecked(bool(island_cfg.get('enabled', True)))
        island_callback = getattr(self, 'on_set_dynamic_island_enabled', None)
        if callable(island_callback):
            island_action.toggled.connect(island_callback)
        else:
            island_action.setEnabled(False)
        menu.removeAction(island_action)
        actions = menu.actions()
        controls_action = next(
            (action for action in actions if action.text().strip() == '桌宠控制'), None)
        if controls_action is not None:
            menu.insertAction(controls_action, island_action)
        else:
            codex_index = actions.index(submenu_action)
            next_action = actions[codex_index + 1] if codex_index + 1 < len(actions) else None
            if next_action is None:
                menu.addAction(island_action)
            else:
                menu.insertAction(next_action, island_action)

        add_action(submenu, '查询并显示额度', None,
                   self._request_codex_quota_now, close_on_trigger=True)
        submenu.addSeparator()
        opener = getattr(self, 'on_open_modern_settings', None)
        if opener is not None:
            add_action(submenu, '详细设置…', 'settings', self._open_codex_settings,
                       close_on_trigger=True)
        # The root menu's modern check layer is installed before this extension
        # creates its submenu, so attach the same visible check painter here.
        if str(menu.property('menuStyle') or '') == 'modern':
            from pet.context_menus.menu_styles.modern import install_modern_check_indicators
            install_modern_check_indicators(submenu)

    def _open_codex_settings(self):
        opener = getattr(self, 'on_open_modern_settings', None)
        if not callable(opener):
            return
        opener()

        def focus_codex_settings():
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if (widget.windowTitle() == '桌宠设置'
                        and hasattr(widget, 'search_edit')):
                    widget.search_edit.setText('Codex')
                    widget.raise_()
                    return

        QTimer.singleShot(120, self, focus_codex_settings)

    def _apply_codex_display_settings(self):
        if not hasattr(self, '_codex_chip'):
            return
        settings = self._codex_display_settings()
        enabled = bool(settings['enabled'])
        if not enabled:
            self._codex_chip.hide()
            self._codex_chip_mode = None
        elif self._codex_state.active:
            self._show_codex_activity_chip()
        elif self._codex_chip_mode == 'quota' and not settings['show_quota']:
            self._codex_chip.hide()
            self._codex_chip_mode = None
        elif (settings['show_quota'] and not self._codex_state.active
              and self._codex_last_quota and self._codex_chip_mode != 'complete'):
            self._show_codex_quota()

    def _expire_codex_chip(self, generation, mode):
        if (generation == self._codex_generation and self._codex_chip_mode == mode
                and mode == 'complete'):
            self._codex_chip.hide()
            self._codex_chip_mode = None

    def _show_codex_quota(self, *, force=False):
        settings = self._codex_display_settings()
        if ((not force and (not settings['enabled'] or not settings['show_quota']))
                or not self._codex_last_quota):
            self._codex_chip.hide()
            return
        self._show_codex_chip(self._codex_last_quota, 'quota')
        if not settings['quota_persistent']:
            seconds = max(1, min(300, int(settings['quota_duration_seconds'])))
            generation = self._codex_generation
            QTimer.singleShot(seconds * 1000, self,
                              lambda g=generation: self._expire_quota_chip(g))

    def _show_codex_activity_chip(self):
        settings = self._codex_display_settings()
        if not settings['enabled']:
            self._codex_chip.hide()
            self._codex_chip_mode = None
            return
        lines = []
        if settings['show_activity']:
            lines.append('对话中 ···')
        if settings['show_quota']:
            lines.append(self._codex_last_quota or '正在查询额度…')
        if not lines:
            self._codex_chip.hide()
            self._codex_chip_mode = None
            return
        self._show_codex_chip('\n'.join(lines), 'active')
        if settings['show_quota'] and not self._codex_last_quota:
            self._request_codex_quota(self._codex_generation)

    def _expire_quota_chip(self, generation):
        if (generation == self._codex_generation and self._codex_chip_mode == 'quota'
                and not self._codex_state.active
                and not self._codex_display_settings()['quota_persistent']):
            self._codex_chip.hide()
            self._codex_chip_mode = None

    def _poll_codex_events(self):
        self._codex_poll_count += 1
        if self._codex_poll_count == 1:
            log.info('Codex link polling started')
        settings = self._codex_display_settings()
        if settings != self._codex_applied_settings:
            self._codex_applied_settings = settings
            self._apply_codex_display_settings()
        self._position_codex_chip()
        events = self._codex_feed.read()
        if events:
            log.info('Codex link read %d event(s)', len(events))
        for event in events:
            transition = self._codex_state.apply(event)
            if transition:
                log.info('Codex link: %s; active turns=%d', transition, len(self._codex_state.active))
            if transition == 'start':
                self._codex_generation += 1
                settings = self._codex_display_settings()
                if settings['enabled'] and (settings['show_activity'] or settings['show_quota']):
                    self._reveal_for_codex()
                if settings['enabled'] and (settings['show_activity'] or settings['show_quota']):
                    self._show_codex_activity_chip()
                else:
                    self._codex_chip.hide()
                    self._codex_chip_mode = None
            elif transition == 'concurrent':
                self._codex_generation += 1
                settings = self._codex_display_settings()
                if settings['enabled'] and (settings['show_activity'] or settings['show_quota']):
                    self._reveal_for_codex()
                    self._show_codex_activity_chip()
                else:
                    self._codex_chip.hide()
                    self._codex_chip_mode = None
            elif transition in ('stop', 'interrupt'):
                self._codex_generation += 1
                generation = self._codex_generation
                message = '这轮对话完成啦' if transition == 'stop' else '这轮对话先停下啦'
                settings = self._codex_display_settings()
                show_message = (settings['enabled'] and
                                (settings['show_completion'] if transition == 'stop'
                                 else settings['show_interrupt']))
                if show_message:
                    self._show_codex_chip(message, 'complete')
                    QTimer.singleShot(4000, self,
                                      lambda g=generation: self._expire_codex_chip(g, 'complete'))
                else:
                    self._codex_chip.hide()
                    self._codex_chip_mode = None
                if settings['enabled'] and settings['show_quota']:
                    QTimer.singleShot(1800, self,
                                      lambda g=generation: self._request_codex_quota(g))
                QTimer.singleShot(18000, self, lambda g=generation: self._end_codex_reveal(g))

    def _position_codex_chip(self):
        if not self._codex_chip.isVisible():
            return
        if not self.isVisible():
            self._codex_chip.hide()
            return
        anchor = self.visible_content_rect()
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        x = max(available.left(), min(anchor.center().x() - self._codex_chip.width() // 2,
                                      available.right() - self._codex_chip.width() + 1))
        y = max(available.top(), anchor.top() - self._codex_chip.height() - 7)
        self._codex_chip.move(x, y)

    def _show_codex_chip(self, message, mode):
        self._codex_chip_mode = mode
        self._codex_chip.setText(message)
        self._codex_chip.adjustSize()
        if self.isVisible():
            self._codex_chip.show()
            self._position_codex_chip()
            self._codex_chip.raise_()
        log.info('Codex link: %s chip %s', mode, message)

    def _on_fullscreen_changed(self, hit):
        # A game on the other monitor may be fullscreen while Codex is active.
        # Keep the status visible only for the bounded Codex notification.
        if getattr(self, '_codex_visibility_override', False):
            return
        result = super()._on_fullscreen_changed(hit)
        if not hasattr(self, '_codex_chip'):
            return result
        if not self.isVisible():
            self._codex_chip.hide()
        elif (self._codex_last_quota and not self._codex_state.active
              and not self._codex_chip.isVisible()):
            self._show_codex_quota()
        return result

    def _reveal_for_codex(self):
        self._codex_visibility_override = True
        if not getattr(self, '_auto_hidden', False) or self.isVisible():
            return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        self._codex_previous_position = QPoint(self.pos())
        x = max(available.left(), available.right() - self.width() - 40)
        y = max(available.top(), available.bottom() - self.height() - 50)
        self._codex_reveal_position = QPoint(x, y)
        self.move(self._codex_reveal_position)
        self._auto_hidden = False
        self.show()
        self.raise_()
        self._codex_revealed_from_fullscreen = True
        log.info('Codex link: temporarily revealed on primary screen at (%d,%d)', x, y)

    def _end_codex_reveal(self, generation):
        if generation != self._codex_generation or self._codex_state.active:
            return
        self._codex_visibility_override = False
        if self._codex_revealed_from_fullscreen:
            if self.pos() == self._codex_reveal_position:
                self.move(self._codex_previous_position)
            self._codex_revealed_from_fullscreen = False
            self._codex_previous_position = None
            self._codex_reveal_position = None
        if getattr(self, 'auto_hide_fullscreen', False):
            hit, _reason = self._fg_fullscreen_probe()
            if hit:
                super()._on_fullscreen_changed(True)
        log.info('Codex link: restored normal fullscreen visibility')

    def _request_codex_quota(self, generation, *, manual=False):
        if generation != self._codex_generation:
            return
        self._codex_quota_request_id += 1
        request_id = self._codex_quota_request_id
        if manual and not self._codex_state.active:
            self._show_codex_chip('正在查询额度…', 'query')

        def worker():
            try:
                result = quota_text(read_quota())
            except Exception as exc:
                log.info('Codex quota unavailable: %s', exc)
                result = 'Codex 额度暂时查不到'
            try:
                self._codex_quota_ready.emit(generation, request_id, result, manual)
            except RuntimeError:
                # The pet may have exited before the read-only query completed.
                pass

        threading.Thread(target=worker, name='nyanko-codex-quota', daemon=True).start()

    def _request_codex_quota_now(self):
        self._request_codex_quota(self._codex_generation, manual=True)

    def _on_codex_quota_ready(self, generation, request_id, message, manual):
        if (generation != self._codex_generation
                or request_id != self._codex_quota_request_id):
            return
        log.info('Codex link: quota query completed manual=%s', manual)
        unavailable = message in ('Codex 额度暂时查不到', '额度暂时查不到')
        if not unavailable:
            self._codex_last_quota = message
        elif not self._codex_last_quota:
            self._codex_last_quota = message
        if self._codex_state.active:
            self._show_codex_activity_chip()
            return
        if manual:
            if unavailable:
                self._show_codex_chip(message, 'query_error')
                QTimer.singleShot(5000, self,
                                  lambda g=generation, r=request_id: self._expire_manual_query(g, r))
            else:
                self._show_codex_quota(force=True)
            return
        settings = self._codex_display_settings()
        if settings['enabled'] and settings['show_quota']:
            if unavailable and not self._codex_last_quota:
                self._codex_last_quota = message
            self._show_codex_quota()
        QTimer.singleShot(1200, self, lambda g=generation: self._end_codex_reveal(g))

    def _expire_manual_query(self, generation, request_id):
        if (generation == self._codex_generation and request_id == self._codex_quota_request_id
                and self._codex_chip_mode == 'query_error'):
            self._codex_chip.hide()
            self._codex_chip_mode = None

    def _commit(self, candidate, clip):
        if clip is None:
            self.choreography = candidate
            return True
        if candidate.routine in WALKS and clip == ROUTINES[candidate.routine][1]:
            # Do not start a new step when interaction or the screen edge
            # prevents it. Settle on the actual side before another action.
            if not self._can_roam() or self._walk_room(candidate.routine) < 4:
                clip = ROUTINES[candidate.routine][2]
                candidate.current = clip
        if clip in RUNS:
            direction = RUN_DIRECTION[clip]
            if not self._can_roam() or self._walk_room(direction) < 216 * self.scale:
                return self._commit(Choreography(), IDLE)
        if super()._switch(clip):
            self.choreography = candidate
            if candidate.routine in WALKS or clip in RUNS:
                self.facing = 'left' if candidate.routine == LEFT or clip == RUN_LEFT else 'right'
            if candidate.routine in WALKS and clip == ROUTINES[candidate.routine][1]:
                self._attach_walk_plan()
            elif clip in RUNS:
                self._attach_run_plan(clip)
            self.routine_history.append(clip)
            self.routine_history[:] = self.routine_history[-64:]
            if clip in (NAP, SNACK, LEFT, RIGHT, *RUNS, ALERT, CUP, SQUID, SHRIMP,
                        JUMP, GUARD, STRETCH, POUNCE):
                if clip in (NAP, SNACK):
                    self._previous_routine = clip
                self._calm_cycles = 0
            if clip == IDLE and self.routine_history[-2:-1] != [IDLE]:
                self._calm_cycles = 0
                self._idle_target = random.randint(4, 7)
            log.info('Nyanko animation: %s | position=(%d,%d)', clip, self.x(), self.y())
            return True
        # The engine restored a playable clip. Do not commit a phase which
        # never started, or let a stale retry bypass the choreography later.
        self._cancel_pending_switch_retry()
        if self.anim != self.choreography.current:
            self.choreography = Choreography()
            super()._switch(IDLE)
        log.warning('Nyanko phase refused; retained playable state: %s', self.anim)
        return False

    def _switch(self, name, _link_request=False):
        if self.choreography is None:
            return super()._switch(name, _link_request)
        if name == DRAG and self._dragging and not getattr(self, '_nyanko_resuming', False):
            progress = 0.0
            if self.movie is not None:
                if self.anim == RELEASE:
                    progress = 1-self.movie.currentFrameNumber()/max(1,self.lib.frames(RELEASE)-2)
                elif self.anim == DRAG:
                    progress = 1.0
            self._landing_timer.stop()
            self._manual_walk = None
            self._manual_walk_timer.stop()
            self._cancel_move()
            candidate = Choreography(current=DRAG_ENTER)
            ok = self._commit(candidate, DRAG_ENTER)
            if ok and progress > 0:
                self.movie.jumpToFrame(round(min(1,progress)*max(1,self.lib.frames(DRAG_ENTER)-2)))
            return ok
        if self._nyanko_releasing and name == IDLE:
            # The upstream release handler requests idle before clearing drag.
            # Start the character's settle only after the handler has finished.
            return True
        if self.choreography.current in (DRAG_ENTER, DRAG) and not getattr(self, '_nyanko_resuming', False):
            return False
        if getattr(self, '_nyanko_resuming', False) and name == self.choreography.current:
            result = super()._switch(name, _link_request)
            if result and self.choreography.routine in WALKS and name == ROUTINES[self.choreography.routine][1]:
                self._attach_walk_plan()
            return result
        if name not in PUBLIC:
            return False
        if name == JUMP and (self._dragging or self._physics_mode is not None):
            return False
        if name in RUNS and self.choreography.current == IDLE:
            if not self._can_roam() or self._walk_room(RUN_DIRECTION[name]) < 216 * self.scale:
                return False
        if name in WALKS and self.choreography.current == IDLE:
            if not self._can_roam():
                return False
            if self._walk_room(name) < 4:
                opposite = RIGHT if name == LEFT else LEFT
                if self._walk_room(opposite) < 4:
                    return False
                name = opposite
        candidate = copy(self.choreography)
        return self._commit(candidate, candidate.request(name))

    def _resume_activity(self):
        self._nyanko_resuming = True
        try:
            super()._resume_activity()
        finally:
            self._nyanko_resuming = False

    def _on_click(self):
        if self.choreography is None:
            return super()._on_click()
        if self._just_dragged:
            return
        self.mark_activity()
        action = CLICK if self._click_counter % 2 == 0 else PROTEST
        self._click_counter += 1
        self._switch(action)

    def mouseReleaseEvent(self, event):
        was_dragging = self._dragging
        if was_dragging and self.choreography is not None:
            self._release_progress = (
                self.movie.currentFrameNumber() / max(1, self.lib.frames(DRAG_ENTER)-2)
                if self.anim == DRAG_ENTER and self.movie is not None else 1.0
            )
        self._nyanko_releasing = bool(was_dragging and self.choreography is not None)
        try:
            super().mouseReleaseEvent(event)
        finally:
            self._nyanko_releasing = False
        if was_dragging and not self._dragging and self.choreography is not None:
            if self._physics_mode is not None:
                self._landing_timer.start()
            else:
                self._start_settle()

    def _start_settle(self):
        self._landing_timer.stop()
        if self._dragging or self.choreography.current not in (DRAG_ENTER, DRAG):
            return
        if self._commit(Choreography(current=RELEASE), RELEASE):
            start = round((1-max(0,min(1,self._release_progress))) * max(1,self.lib.frames(RELEASE)-2))
            if start:
                self.movie.jumpToFrame(start)

    def _finish_throw_feedback(self):
        if getattr(self, '_closing', False):
            self._landing_timer.stop()
        elif not self._dragging and self._physics_mode is None:
            self._start_settle()

    def _on_anim_ended(self, name):
        if self.choreography is None:
            return super()._on_anim_ended(name)
        if self._hidden_paused or getattr(self, '_closing', False):
            return
        if name != self.choreography.current:
            return
        if name in (DRAG_ENTER, DRAG):
            if self._dragging or self._physics_mode is not None:
                self._release_progress = 1.0
                self._commit(Choreography(current=DRAG), DRAG)
            else:
                self._start_settle()
            return
        if self._move_plan:
            self._advance_walk(1)
        if name == IDLE and self.choreography.pending is None:
            return self._pick_next()
        candidate = copy(self.choreography)
        self._commit(candidate, candidate.finished(name))

    def _pick_next(self):
        if self.choreography is None:
            return super()._pick_next()
        if self._hidden_paused or getattr(self, '_closing', False):
            return
        if self.choreography.current != IDLE:
            return
        self._calm_cycles += 1
        if self._dragging or self._context_menu_open or self._calm_cycles < self._idle_target:
            self._switch(IDLE)
        else:
            slot = self._daily_phase % 6
            if slot == 4:
                self._switch(CUP)
            elif slot == 5:
                preferred = RUN_LEFT if self.facing == 'left' else RUN_RIGHT
                if self._walk_room(RUN_DIRECTION[preferred]) < 216 * self.scale:
                    preferred = RUN_RIGHT if preferred == RUN_LEFT else RUN_LEFT
                if not self._can_roam() or self._walk_room(RUN_DIRECTION[preferred]) < 216 * self.scale:
                    self._switch(LECTURE)
                else:
                    self._switch(preferred)
            elif slot == 0:
                self._switch(ALERT if self._daily_phase // 6 % 2 == 0 else STRETCH)
            elif slot == 3:
                self._switch((SQUID, SHRIMP, GUARD)[self._daily_phase // 6 % 3])
            elif slot == 1 and self._can_roam():
                preferred = LEFT if self.facing == 'left' else RIGHT
                if self._walk_room(preferred) < 6 * 44 * self.scale:
                    preferred = RIGHT if preferred == LEFT else LEFT
                if not self._switch(preferred):
                    self._switch(IDLE)
            else:
                self._switch(SNACK if self._previous_routine == NAP else NAP)
            self._daily_phase += 1

    def _can_roam(self):
        return not (
            self.no_move or self.lock_position or self._hidden_paused
            or getattr(self, '_closing', False) or self._context_menu_open
            or self._dragging or self._press_global is not None
            or self._physics_mode is not None
        )

    def _walk_bounds(self):
        screen = self._screen_available()
        if screen is None:
            return self.x(), self.x()
        area = screen.availableGeometry()
        # All 328 new frames fit x=146..494 on the 640px canvas. Allow only
        # transparent gutters off-screen, with 6 source pixels of clearance.
        gutter = int(140 * self.scale)
        lo = area.left() - gutter
        hi = max(lo, area.right() + 1 - self.width() + gutter)
        return lo, hi

    def _walk_room(self, direction):
        lo, hi = self._walk_bounds()
        return max(0, self.x()-lo if direction == LEFT else hi-self.x())

    def _attach_walk_plan(self):
        state = self.choreography
        if not self._can_roam() or state.routine not in WALKS:
            return
        direction = -1 if state.routine == LEFT else 1
        lo, hi = self._walk_bounds()
        start = self.x()
        target = min(hi, max(lo, start + direction * 44 * self.scale))
        self._move_plan = {
            'start_x': start, 'target_x': target, 'start_y': self.y(),
            'duration': max(1/24, (self.lib.frames(self.anim)-1)/24),
            'nyanko_clip': self.anim,
        }
        self._move_timer.start()

    @staticmethod
    def _run_distance(frame):
        # Same source-frame phase and 216px track used in the reviewed preview.
        j = frame - 32
        if j < 0:
            phase = 0
        elif j < 48:
            phase = (j / 48) ** 2
        elif j < 72:
            phase = 1 + (j - 48) / 24
        elif j < 120:
            u = (j - 72) / 48
            phase = 2 + 2 * u - u * u
        else:
            phase = 3
        return 72 * phase

    def _attach_run_plan(self, clip):
        direction = RUN_DIRECTION[clip]
        if not self._can_roam() or self._walk_room(direction) < 216 * self.scale:
            return
        sign = -1 if clip == RUN_LEFT else 1
        self._move_plan = {
            'start_x': self.x(), 'target_x': self.x() + sign * 216 * self.scale,
            'start_y': self.y(), 'nyanko_clip': clip, 'run_sign': sign,
        }
        self._move_timer.start()

    def _advance_walk(self, progress):
        plan = self._move_plan
        if not plan or plan.get('nyanko_clip') != self.anim:
            return
        if not self._can_roam():
            self._cancel_move()
            if self.choreography.routine in WALKS and self.choreography.pending is None:
                self.choreography.request(IDLE)
            return
        lo, hi = self._walk_bounds()
        goal = min(hi, max(lo, plan['target_x']))
        if 'run_sign' in plan:
            frame = round(min(1,max(0,progress)) * max(1,self.lib.frames(self.anim)-1))
            x = plan['start_x'] + plan['run_sign'] * self._run_distance(frame) * self.scale
        else:
            x = plan['start_x'] + (goal-plan['start_x']) * min(1,max(0,progress))
        self.move(int(round(min(hi,max(lo,x)))), plan['start_y'])

    def _on_move_tick(self):
        if self.choreography is None:
            return super()._on_move_tick()
        if self._move_plan and self.movie is not None:
            # Both frame callbacks and timer ticks use the displayed source
            # frame. currentTimeSeconds() is divided by playback speed and
            # would pull the window backwards between frame callbacks.
            self._advance_walk(self.movie.currentFrameNumber()/max(1,self.lib.frames(self.anim)-1))

    def _on_frame(self, name, n):
        if self.choreography is not None and name == self.anim and self._move_plan:
            self._advance_walk(n/max(1,self.lib.frames(name)-1))
        return super()._on_frame(name,n)

    def _trigger_move(self, name):
        if self.choreography is None:
            return super()._trigger_move(name)
        self.mark_activity()
        self._manual_walk = name
        if self._context_menu_open:
            self._manual_walk_timer.start(0)
        else:
            self._dispatch_manual_walk()

    def _dispatch_manual_walk(self):
        if getattr(self, '_closing', False):
            self._manual_walk = None
            return
        if self._context_menu_open:
            self._manual_walk_timer.start(25)
            return
        name, self._manual_walk = self._manual_walk, None
        if name is not None:
            self._switch(name)

    def _try_move(self, name=None):
        if self.choreography is None:
            return super()._try_move(name)
        return self._switch(name or (LEFT if self.facing == 'left' else RIGHT))

    def set_no_move(self, on):
        super().set_no_move(on)
        if on and self.choreography is not None and (
            self.choreography.routine in WALKS or self.choreography.current in RUNS
        ):
            self._cancel_move()
            self.choreography.request(IDLE)

    def _predict_prewarm(self, name, n):
        if self.choreography is None:
            return super()._predict_prewarm(name, n)
        # The original random predictor does not know enter/loop/exit phases.
        # High-priority and delayed library warming still handle actual clips.
