from collections import deque

class Task:
    def __init__(self, action, payload=None, parent=None):
        """
        Represents a single task in the HTN queue.

        Args:
            action (str): The action type (e.g., "craft", "gather", "move")
            payload: Item id, resource, or other action-specific data
            parent (str): The high-level intention that spawned this task
        """
        self.action = action      # e.g., "craft", "gather", "move"
        self.payload = payload    # item id or resource
        self.parent = parent      # intention spawning this task

    def __repr__(self):
        return f"Task(action={self.action}, payload={self.payload}, parent={self.parent})"

class TaskQueue:
    def __init__(self):
        """
        FIFO queue for managing hierarchical task decomposition.
        """
        self.q = deque()

    def push(self, task):
        """
        Add a task to the end of the queue.

        Args:
            task (Task): Task to add
        """
        self.q.append(task)

    def push_many(self, tasks):
        """
        Add multiple tasks to the queue.

        Args:
            tasks (list[Task]): List of tasks to add
        """
        for t in tasks:
            self.push(t)

    def pop(self):
        """
        Remove and return the first task from the queue.

        Returns:
            Task or None: The next task, or None if queue is empty
        """
        return self.q.popleft() if self.q else None

    def empty(self):
        """
        Check if the queue is empty.

        Returns:
            bool: True if queue is empty, False otherwise
        """
        return len(self.q) == 0

    def size(self):
        """
        Get the number of tasks in the queue.

        Returns:
            int: Number of tasks
        """
        return len(self.q)

    def peek(self):
        """
        View the first task without removing it.

        Returns:
            Task or None: The next task, or None if queue is empty
        """
        return self.q[0] if self.q else None

    def clear(self):
        """
        Remove all tasks from the queue.
        """
        self.q.clear()
