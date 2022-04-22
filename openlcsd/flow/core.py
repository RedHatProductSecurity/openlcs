import logging
from workflow.engine import GenericWorkflowEngine
from workflow.engine import ProcessingFactory
from workflow.engine import TransitionActions
from workflow.utils import classproperty


class OpenlcsWorkflowEngine(GenericWorkflowEngine):
    """
    Used to execute set of methods in a specified order.
    """

    @classproperty
    # pylint: disable=no-self-argument
    def processing_factory(cls):
        """Provide a processing factory."""
        return OpenlcsProcessingFactory

    def init_logger(self):
        """Return the appropriate logger instance."""
        return logging.getLogger(
            "workflow.%s" % self.__class__)


class OpenlcsProcessingFactory(ProcessingFactory):
    """Processing factory for persistence requirements."""

    # We also have our own `transition_actions`
    @classproperty
    # pylint: disable=no-self-argument
    def transition_exception_mapper(cls):
        """Set a transition exception mapper for actions while processing.
        """
        return OpenlcsTransitionActions

    @staticmethod
    def before_processing(eng, objects):
        """Standard pre-processing callback.

        Save a pointer to the processed objects.
        """
        super(OpenlcsProcessingFactory, OpenlcsProcessingFactory).before_processing(    # noqa 
                eng, objects)

    @staticmethod
    def after_processing(eng, objects):
        """Standard post-processing callback; basic cleaning."""
        super(OpenlcsProcessingFactory, OpenlcsProcessingFactory).after_processing(    # noqa
                eng, objects)


class OpenlcsTransitionActions(TransitionActions):
    """
    Actions to take when WorkflowTransition exceptions are raised.
    """

    @staticmethod
    def HaltProcessing(obj, eng, callbacks, exc_info):
        """Interrupt the execution of the engine."""
        super(OpenlcsTransitionActions, OpenlcsTransitionActions).HaltProcessing(    # noqa
                obj, eng, callbacks, exc_info)

    @staticmethod
    def StopProcessing(obj, eng, callbacks, exc_info):
        """Gracefully stop the execution of the engine."""
        super(OpenlcsTransitionActions, OpenlcsTransitionActions).StopProcessing(    # noqa
                obj, eng, callbacks, exc_info)

    @staticmethod
    def Exception(obj, eng, callbacks, exc_info):
        """Action to take when an unhandled exception is raised.

        FIXME: clean up/logging goes here in terms of exceptions.
        """
        super(OpenlcsTransitionActions, OpenlcsTransitionActions).Exception(
                obj, eng, callbacks, exc_info)
