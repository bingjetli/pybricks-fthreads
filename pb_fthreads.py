from pybricks.tools import wait, run_task, multitask, StopWatch

DEBUG_ENABLED = True


def _log(input):
    if DEBUG_ENABLED == True:
        print(input)


class FThreadPool:
    ## This is the list of async __thread functions responsible for executing any
    # tasks added to the task queue.
    __thread_pool = None

    ## This is a simple queue of tasks that can be enqueued or dequeued and contains
    # tasks for the __task functions to execute.
    __task_queue = None

    ## A simple mutex lock to ensure that only 1 __thread function can access the shared
    # variables at a time.
    __mutex_lock = None

    ## This is a variable that keeps track of the active tasks in the task pool. When this
    # variable reaches 0, then all the tasks will automatically shutdown.
    __active_threads = None

    ## This flag is used to signal that the shutdown process has started. Meaning that
    # all idle threads should exit and the thread pool should stop accepting new tasks.
    __shutdown_flag = None

    def __init__(self, pool_size):
        self.__thread_pool = [self.__thread(i) for i in range(pool_size)]
        self.__task_queue = []
        self.__mutex_lock = False
        self.__active_threads = 0
        self.__shutdown_flag = False

        _log("Initialized FThreadPool with {} threads".format(pool_size))

    def __acquire_lock(self, identifier=None):
        while self.__mutex_lock:
            ## Block until the queue is unlocked.
            continue
        self.__mutex_lock = True
        if identifier is not None:
            _log("{} acquired the mutex lock".format(identifier))
        else:
            _log("The mutex lock was acquired")

    def __release_lock(self, identifier=None):
        self.__mutex_lock = False
        if identifier is not None:
            _log("{} released the mutex lock".format(identifier))
        else:
            _log("The mutex lock was released")

    async def __thread(self, thread_id):
        current_task = None

        acquire_lock = self.__acquire_lock("Thread {}".format(thread_id))
        release_lock = self.__release_lock("Thread {}".format(thread_id))

        while True:
            ## First, check if there is a task assigned...
            if current_task is not None:
                _log(
                    "#{}, there is a task assigned, executing task...".format(thread_id)
                )
                await current_task[0](
                    *current_task[1],
                    **current_task[2],
                    thread_id=thread_id,
                    thread_pool=self,
                )
                _log(
                    "#{}, + task completed, decrementing the active tasks..".format(
                        thread_id
                    )
                )

                self.__acquire_lock("Thread {}".format(thread_id))
                self.__active_threads -= 1
                self.__release_lock("Thread {}".format(thread_id))

                current_task = None

                await wait(1)
                continue

            ## If there is no task assigned, check if the shutdown flag is set...
            self.__acquire_lock("Thread {}".format(thread_id))
            if self.__shutdown_flag == True:
                _log(
                    "#{}, the shutdown flag is set, breaking out of the loop...".format(
                        thread_id
                    )
                )
                self.__release_lock("Thread {}".format(thread_id))
                break

            ## This implies that the shutdown flag is not set yet, so we should check
            # if there are any tasks inside the task queue that needs to be assigned...
            if len(self.__task_queue) > 0:
                _log(
                    "#{}, there are unassigned tasks inside the queue, so we assign a task to this coroutine...".format(
                        thread_id
                    )
                )
                current_task = self.__task_queue.pop(0)
                self.__active_threads += 1
                self.__release_lock("Thread {}".format(thread_id))
                await wait(1)
                continue

            ## This implies that the shutdown flag is not set yet, and there are no
            # tasks inside the task queue that needs to be assigned, so we should
            # check if there are any active __task functions that are running...
            if self.__active_threads == 0:
                _log(
                    "#{}, there are no active __task functions running, so we will begin shutting down.".format(
                        thread_id
                    )
                )
                self.__shutdown_flag = True
                self.__release_lock("Thread {}".format(thread_id))
                _log("#{}, released the task queue lock".format(thread_id))
                await wait(1)
                continue

            ## This implies that there are still active __task functions running, but
            # there are no unassigned tasks inside the task queue. So in that case, we will
            # remain on standby for more tasks to enter the task queue or wait for the active
            # __task functions to finish.
            self.__release_lock("Thread {}".format(thread_id))
            _log("#{}, standing by..".format(thread_id))
            await wait(1)
        _log("#{} : Shutdown successfully".format(thread_id))

    def spawn(self, task, *args, **kwargs):
        self.__acquire_lock()
        if self.__shutdown_flag == False:
            ## Only add tasks if the pool is not shutting down.
            self.__task_queue.append((task, args, kwargs))
        self.__release_lock()

    def run(self):
        run_task(multitask(*self.__thread_pool))
