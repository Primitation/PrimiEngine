from .logger import Logger, LogMode


class LogSubsystem:

    def __init__(self):

        self._logger = Logger()

    def get(self, name: str):

        return self._logger.get(name)

    def verbose(self):

        self._logger.set_mode(
            LogMode.DEBUG
        )

    def normal(self):

        self._logger.set_mode(
            LogMode.RELEASE
        )

    def errors(self):

        self._logger.set_mode(
            LogMode.QUIET
        )

    def enable_console(self):

        self._logger.enable_console()

    def disable_console(self):

        self._logger.disable_console()

    def enable_file(self, file: str = "logs/latest.log"):

        self._logger.enable_file(file)

    def disable_file(self):

        self._logger.disable_file()

    def close(self):

        self._logger.close()


# Global logging system
Log = LogSubsystem()
