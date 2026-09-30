"""Nyanko's finite routines. All decisions run on Qt's GUI thread."""
from dataclasses import dataclass

IDLE = '坐着发呆'
CLICK = '斜眼不满'
NAP = '趴下来歇一会'
SNACK = '拿团子吃'
LEFT = '向左散步'
RIGHT = '向右散步'
RUN_LEFT = '向左小跑'
RUN_RIGHT = '向右小跑'
ALERT = '警觉探看'
CUP = '举杯小酌'
SQUID = '吃烤鱿鱼'
SHRIMP = '吃炸虾'
JUMP = '轻跳落地'
GUARD = '护食抱团子'
STRETCH = '伸懒腰'
POUNCE = '扑空小踉跄'
PROTEST = '抬爪抗议'
LECTURE = '得意说教'
DRAG = '悬空不满'
DRAG_ENTER = '拖起悬空'
RELEASE = '松手坐稳'
INTERACTIONS = (DRAG_ENTER, DRAG, RELEASE)
WALKS = (LEFT, RIGHT)
RUNS = (RUN_LEFT, RUN_RIGHT)
MOVES = WALKS + RUNS
RUN_DIRECTION = {RUN_LEFT: LEFT, RUN_RIGHT: RIGHT}
TURN_TO = {LEFT: '站着转向左', RIGHT: '站着转向右'}
ROUTINES = {
    NAP: (NAP, '趴睡呼吸', '起身坐好', 3),
    SNACK: (SNACK, '团子咀嚼', '收好团子', 2),
    LEFT: (LEFT, '左行小步', '左向停步坐好', 6),
    RIGHT: (RIGHT, '右行小步', '右向停步坐好', 6),
}
PUBLIC = (IDLE, CLICK, NAP, SNACK, LEFT, RIGHT, PROTEST, LECTURE,
          ALERT, CUP, SQUID, SHRIMP, JUMP, GUARD, STRETCH, POUNCE, *RUNS)
ALL_CLIPS = {IDLE, CLICK, PROTEST, LECTURE, ALERT, CUP, SQUID, SHRIMP,
             JUMP, GUARD, STRETCH, POUNCE, *RUNS, *INTERACTIONS, *TURN_TO.values()} | {n for r in ROUTINES.values() for n in r[:3]}


@dataclass
class Choreography:
    current: str = IDLE
    routine: str | None = None
    remaining: int = 0
    pending: str | None = None

    def _begin(self, action):
        self.pending = None
        self.routine = action if action in ROUTINES else None
        self.remaining = ROUTINES[action][3] if self.routine else 0
        self.current = action
        return action

    def request(self, action):
        if action not in PUBLIC:
            raise ValueError(action)
        if action in (CLICK, PROTEST) and self.current in (CLICK, PROTEST):
            return None
        if action in WALKS and action == self.routine and self.current != ROUTINES[action][2]:
            return None
        if self.current == IDLE:
            return self._begin(action)
        # One pending intention; repeated clicks never build an unbounded queue.
        self.pending = action
        return None

    def finished(self, name):
        if name != self.current:
            return None
        if self.routine:
            enter, loop, leave, _ = ROUTINES[self.routine]
            if name in TURN_TO.values():
                self.current = leave if self.pending is not None else loop
            elif name == enter:
                self.current = leave if self.pending is not None else loop
            elif name == loop:
                self.remaining -= 1
                if self.routine in WALKS and self.pending in WALKS and self.pending != self.routine:
                    self.routine = self.pending
                    self.pending = None
                    self.remaining = ROUTINES[self.routine][3]
                    self.current = TURN_TO[self.routine]
                else:
                    self.current = leave if self.pending is not None or self.remaining <= 0 else loop
            else:
                return self._begin(self.pending or IDLE)
            return self.current
        return self._begin(self.pending or IDLE)
