from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index, ForeignKey
from sqlalchemy.orm import Session, declared_attr

from database import Base


class BaseModelC(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted = Column(Boolean, default=False, nullable=False)

    @declared_attr
    def __table_args__(cls):
        if cls.__dict__.get('__abstract__', False):
            return ()  # No table args for abstract base class
        return (
            Index(f"idx_{cls.__tablename__}_created_at", "created_at"),
            Index(f"idx_{cls.__tablename__}_deleted", "deleted"),
        )

    def save(self, db: Session):
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session):
        """Soft delete the record"""
        self.deleted = True
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    def hard_delete(self, db: Session):
        """Hard delete the record from the database"""
        db.delete(self)
        db.commit()
        return None

    @classmethod
    def find(cls, db: Session, include_deleted: bool = False, **filters):
        """Query records, excluding deleted by default"""
        query = db.query(cls)
        if not include_deleted:
            query = query.filter(cls.deleted == False)
        for key, value in filters.items():
            query = query.filter(getattr(cls, key) == value)
        return query

    @classmethod
    def find_one(cls, db: Session, include_deleted: bool = False, **filters):
        """Query a single record, excluding deleted by default"""
        query = cls.find(db, include_deleted=include_deleted, **filters)
        return query.first()

    @classmethod
    def get(cls, db: Session, id: int, include_deleted: bool = False):
        """Get a record by ID, excluding deleted by default"""
        return cls.find_one(db, include_deleted=include_deleted, id=id)

    @classmethod
    def find_all(cls, db: Session, include_deleted: bool = False):
        """Find all records, excluding deleted by default"""
        return cls.find(db, include_deleted=include_deleted).all()

    @classmethod
    def find_deleted(cls, db: Session):
        """Find only deleted records"""
        return db.query(cls).filter(cls.deleted == True).all()

    @classmethod
    def count_documents(cls, db: Session, include_deleted: bool = False, **filters):
        """Count records, excluding deleted by default"""
        query = db.query(cls)
        if not include_deleted:
            query = query.filter(cls.deleted == False)
        for key, value in filters.items():
            query = query.filter(getattr(cls, key) == value)
        return query.count()


class BaseModelCU(BaseModelC):
    __abstract__ = True

    updated_at = Column(DateTime, nullable=True)

    @declared_attr
    def __table_args__(cls):
        if cls.__dict__.get('__abstract__', False):
            return ()  # No table args for abstract base class
        return (
            Index(f"idx_{cls.__tablename__}_created_at", "created_at"),
            Index(f"idx_{cls.__tablename__}_deleted", "deleted"),
        )

    def save(self, db: Session):
        """Save the record with updated_at timestamp"""
        self.updated_at = datetime.now(timezone.utc)
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    def update(self, db: Session, **kwargs):
        """Update the record with updated_at timestamp"""
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc)
        db.add(self)
        db.commit()
        db.refresh(self)
        return self

    def delete(self, db: Session):
        """Soft delete with updated_at timestamp"""
        self.deleted = True
        self.updated_at = datetime.now(timezone.utc)
        db.add(self)
        db.commit()
        db.refresh(self)
        return self


class User(BaseModelCU):
    __tablename__ = "users"

    wallet_address = Column(String, index=True)
    key_count = Column(Integer, default=0)


class UserNFT(BaseModelC):
    __tablename__ = "user_nft"

    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    nft_collection = Column(String)
    nft_id = Column(String)
    used = Column(Boolean, default=False)


class UserSocial(BaseModelC):
    __tablename__ = "user_social"

    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    platform = Column(String)
    handle = Column(String)
