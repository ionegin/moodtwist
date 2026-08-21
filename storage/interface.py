from abc import ABC, abstractmethod

# Это «чертеж» для любого хранилища. 
# Любая база данных (Sheets или SQL) ОБЯЗАНА уметь выполнять эти действия.
class StorageInterface(ABC):
    @abstractmethod
    async def save_daily(self, user_id: int, data: dict, date: str):
        """Сохранение ежедневных цифр"""
        pass

    @abstractmethod
    async def save_note(self, user_id: int, text: str, is_voice: bool, duration: int = 0):
        """Сохранение текстовых или голосовых заметок"""
        pass