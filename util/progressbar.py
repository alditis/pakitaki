import threading
import time
from util import const

def start(self):
    self.progressbar.set_visible(True)
    self.button_process.set_visible(False)
    self.done = False
    self.progress = 0
    self.task = const.TASK_FRAGMENT

    def run():
        while not self.done:
            if self.progress <= const.PERCENTAGE_TASK_FRAGMENT:
                self.progressbar.set_fraction(self.progress)
                time.sleep(const.SLEEP_TASK_FRAGMENT)
            elif self.progress <= const.PERCENTAGE_TASK_FRAGMENT + const.PERCENTAGE_TASK_JOIN:
                self.progress += self.factor_task_join
                self.progressbar.set_fraction(self.progress)
                time.sleep(const.SLEEP_TASK_JOIN)
            elif self.progress <= const.PERCENTAGE_TASK_FRAGMENT + const.PERCENTAGE_TASK_JOIN + const.PERCENTAGE_TASK_DELETE:
                self.progress += self.factor_task_delete
                self.progressbar.set_fraction(self.progress)
                time.sleep(const.SLEEP_TASK_DELETE)

            if self.progress >= 1:
                finish(self)

    self.progressbar_thread = threading.Thread(target = run)
    self.progressbar_thread.daemon = True
    self.progressbar_thread.start()
    self.progressbar_thread_finish = threading.Event()

def finish(self):
    self.progressbar.set_fraction(1)
    self.done = True
    self.process_thread_finish.set()
    self.button_process.set_visible(True)
    self.progressbar.set_visible(False)
    self.progressbar_thread.do_run = False