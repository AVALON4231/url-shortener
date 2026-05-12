from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, user_repo: UserRepository = None):
        self.user_repo = user_repo or UserRepository()

    def register(self, email: str, password: str) -> bool:
        return self.user_repo.create_user(email, password)

    def authenticate(self, email: str, password: str):
        user = self.user_repo.get_user_by_email(email)
        if not user:
            return None
        if not self.user_repo.verify_password(password, user["hashed_password"]):
            return None
        return user