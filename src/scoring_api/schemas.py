"""Pydantic schemas defining the public scoring API contract."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NullableFiniteFloat = FiniteFloat | None
NullableNonEmptyString = NonEmptyString | None


class PredictionRequest(BaseModel):
    """One dossier represented using the 44 inputs expected by the model."""

    model_config = ConfigDict(extra="forbid", strict=True)

    client_ape_division: NullableFiniteFloat
    client_departement: NullableNonEmptyString
    client_effectif: NullableFiniteFloat
    client_idcc: FiniteFloat
    client_nb_prior_dossiers: NonNegativeInt
    client_opco_habituel: NullableNonEmptyString
    client_prior_nb_fails: NonNegativeInt
    client_prior_nb_ok: NonNegativeInt
    client_prior_nb_opcos_distincts: NonNegativeInt
    client_prior_win_rate: NullableFiniteFloat
    client_rang_dossier: NonNegativeInt
    client_tranche_effectif: NonEmptyString
    annee_creation: FiniteFloat
    ape_division: NullableFiniteFloat
    departement_client: NullableNonEmptyString
    duree_sous_seuil_min: bool
    ecart_heures_vs_seuil_min: FiniteFloat
    effectif_client: NullableFiniteFloat
    est_nouvel_opco_pour_client: bool
    funder_max_factures: FiniteFloat
    funder_min_heures_facturable: FiniteFloat
    funder_nom: NonEmptyString
    heures_prevues: PositiveFloat
    idcc: FiniteFloat
    is_premier_dossier: bool
    is_rush_q4: bool
    is_session_ete: bool
    jours_depuis_dernier_dossier: NullableFiniteFloat
    modalite: NullableNonEmptyString
    mois_creation: FiniteFloat
    montant_ca_eur: NonNegativeFloat
    montant_demande_eur: NonNegativeFloat
    opco_habituel_client: NullableNonEmptyString
    pct_financement_demande: NullableFiniteFloat
    source_lead: NullableNonEmptyString
    taux_horaire_demande_eur: PositiveFloat
    thematique: NonEmptyString
    tranche_effectif: NonEmptyString
    trimestre_creation: FiniteFloat
    type_financement: NullableNonEmptyString
    hg_departement_client: NullableNonEmptyString
    hg_idcc: FiniteFloat
    hg_opco_entreprise: NullableNonEmptyString
    hg_taille_entreprise: NullableFiniteFloat


class PredictionResponse(BaseModel):
    """Business response returned by a successful model inference."""

    risk_score: float
    threshold: float
    risk_flag: bool
    model_name: str
    model_version: str
