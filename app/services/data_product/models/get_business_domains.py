from pydantic import BaseModel, Field

class GetBusinessDomainsRequest(BaseModel):
    keyword: str | None = Field(None, description="A keyword to search for business domains. Optional.")

class BusinessDomain(BaseModel):
    id: str = Field(..., description="The unique identifier of the domain.")
    name: str = Field(..., description="The name of the domain.")
    description: str = Field(..., description="A description of the domain.")

class GetBusinessDomainsResponse(BaseModel):
    domains: list[BusinessDomain] = Field(..., description="A list of business domains.")   