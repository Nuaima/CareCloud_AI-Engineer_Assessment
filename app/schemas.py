import re
from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from .models import SexEnum

US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA",
    "ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
    "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
}
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z'\- ]{0,49}$")
ZIP_RE = re.compile(r"^\d{5}(?:-\d{4})?$")

def normalize_phone(v: str | None) -> str | None:
    if v is None:
        return None
    digits = re.sub(r"\D", "", v)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("must be a valid 10-digit U.S. phone number")
    return digits

def parse_dob(v: Any) -> date:
    if isinstance(v, date) and not isinstance(v, datetime):
        parsed = v
    elif isinstance(v, str):
        parsed = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(v, fmt).date()
                break
            except ValueError:
                pass
        if parsed is None:
            raise ValueError("date_of_birth must be MM/DD/YYYY")
    else:
        raise ValueError("date_of_birth must be MM/DD/YYYY")
    if parsed > date.today():
        raise ValueError("date_of_birth cannot be in the future")
    return parsed

class PatientBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    date_of_birth: date
    sex: SexEnum
    phone_number: str
    email: EmailStr | None = None
    address_line_1: str = Field(min_length=1, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    state: str
    zip_code: str
    insurance_provider: str | None = Field(default=None, max_length=150)
    insurance_member_id: str | None = Field(default=None, max_length=100)
    preferred_language: str = Field(default="English", min_length=1, max_length=50)
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not NAME_RE.fullmatch(v):
            raise ValueError("must contain alphabetic characters with optional spaces, hyphens, or apostrophes")
        return v

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def validate_dob(cls, v: Any) -> date:
        return parse_dob(v)

    @field_validator("phone_number", "emergency_contact_phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return normalize_phone(v)

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: str) -> str:
        state = v.strip().upper()
        if state not in US_STATES:
            raise ValueError("must be a valid 2-letter U.S. state abbreviation")
        return state

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str) -> str:
        v = v.strip()
        if not ZIP_RE.fullmatch(v):
            raise ValueError("must be a 5-digit ZIP or ZIP+4")
        return v

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    date_of_birth: date | None = None
    sex: SexEnum | None = None
    phone_number: str | None = None
    email: EmailStr | None = None
    address_line_1: str | None = Field(default=None, min_length=1, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = None
    zip_code: str | None = None
    insurance_provider: str | None = Field(default=None, max_length=150)
    insurance_member_id: str | None = Field(default=None, max_length=100)
    preferred_language: str | None = Field(default=None, min_length=1, max_length=50)
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_phone: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not NAME_RE.fullmatch(v):
            raise ValueError("must contain alphabetic characters with optional spaces, hyphens, or apostrophes")
        return v

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def validate_dob(cls, v: Any) -> date | None:
        if v is None:
            return None
        return parse_dob(v)

    @field_validator("phone_number", "emergency_contact_phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return normalize_phone(v)

    @field_validator("state", mode="before")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        if v is None:
            return None
        state = v.strip().upper()
        if state not in US_STATES:
            raise ValueError("must be a valid 2-letter U.S. state abbreviation")
        return state

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not ZIP_RE.fullmatch(v):
            raise ValueError("must be a 5-digit ZIP or ZIP+4")
        return v

class PatientOut(PatientBase):
    model_config = ConfigDict(from_attributes=True)
    patient_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
