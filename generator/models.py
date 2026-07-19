from pydantic import BaseModel, HttpUrl
from typing import List, Optional

class Link(BaseModel):
    title: str
    url: HttpUrl
    featured: bool = False

class PageConfig(BaseModel):
    username: str
    name: str
    role: Optional[str] = ""
    bio: str
    avatar_initial: str = "N"
    theme: str = "minimal"
    links: List[Link]