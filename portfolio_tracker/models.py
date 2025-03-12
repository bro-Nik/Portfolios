from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import DeclarativeBase, mapped_column, declared_attr

class Base(DeclarativeBase):
    pass
    # id: Mapped[int] = mapped_column(primary_key=True)

# class Base(DeclarativeBase):
#
#     @declared_attr.cascading
#     @classmethod
#     def id(cls):
#         for base in cls.__mro__[1:-1]:
#             if getattr(base, "__table__", None) is not None:
#                     return mapped_column(ForeignKey(base.id), primary_key=True)
#             else:
#                 return mapped_column(Integer, primary_key=True)
