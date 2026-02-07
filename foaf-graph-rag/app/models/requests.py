from pydantic import BaseModel, Field
from typing import Optional


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query about the FoaF network")
    include_metadata: bool = Field(False, description="Include SPARQL query and execution metadata")


class AddPersonRequest(BaseModel):
    name: str = Field(..., description="Full name of the person")
    age: Optional[int] = Field(None, description="Age of the person")
    gender: Optional[str] = Field(None, description="Gender of the person")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    address: Optional[str] = Field(None, description="Full address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State/Province")
    postal_code: Optional[str] = Field(None, description="Postal code")
    country: Optional[str] = Field(None, description="Country")
    job_title: Optional[str] = Field(None, description="Job title")
    occupation: Optional[str] = Field(None, description="Occupation description")
    industry: Optional[str] = Field(None, description="Industry sector")


class AddRelationshipRequest(BaseModel):
    subject: str = Field(..., description="URI or name of the subject person")
    predicate: str = Field(
        ...,
        description="Relationship type (e.g., friendOf, spouseOf, parentOf, childOf, siblingOf, colleagueOf, neighborOf)",
    )
    object: str = Field(..., description="URI or name of the object person")
