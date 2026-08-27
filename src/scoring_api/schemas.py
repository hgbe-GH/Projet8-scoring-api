"""Pydantic schemas defining the public scoring API contract."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
PositiveFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PredictionRequest(BaseModel):
    """One dossier represented using the 44 inputs expected by the model."""

    model_config = ConfigDict(extra="forbid", strict=True)

    client_ape_division: FiniteFloat
    client_departement: NonEmptyString
    client_effectif: FiniteFloat
    client_idcc: FiniteFloat
    client_nb_prior_dossiers: NonNegativeInt
    client_opco_habituel: NonEmptyString
    client_prior_nb_fails: NonNegativeInt
    client_prior_nb_ok: NonNegativeInt
    client_prior_nb_opcos_distincts: NonNegativeInt
    client_prior_win_rate: FiniteFloat
    client_rang_dossier: PositiveInt
    client_tranche_effectif: NonEmptyString
    annee_creation: FiniteFloat
    ape_division: FiniteFloat
    departement_client: NonEmptyString
    duree_sous_seuil_min: NonEmptyString
    ecart_heures_vs_seuil_min: FiniteFloat
    effectif_client: FiniteFloat
    est_nouvel_opco_pour_client: NonEmptyString
    funder_max_factures: FiniteFloat
    funder_min_heures_facturable: FiniteFloat
    funder_nom: NonEmptyString
    heures_prevues: PositiveFloat
    idcc: FiniteFloat
    is_premier_dossier: NonEmptyString
    is_rush_q4: NonEmptyString
    is_session_ete: NonEmptyString
    jours_depuis_dernier_dossier: FiniteFloat
    modalite: NonEmptyString
    mois_creation: FiniteFloat
    montant_ca_eur: NonNegativeFloat
    montant_demande_eur: PositiveFloat
    opco_habituel_client: NonEmptyString
    pct_financement_demande: FiniteFloat
    source_lead: NonEmptyString
    taux_horaire_demande_eur: PositiveFloat
    thematique: NonEmptyString
    tranche_effectif: NonEmptyString
    trimestre_creation: FiniteFloat
    type_financement: NonEmptyString
    hg_departement_client: NonEmptyString
    hg_idcc: FiniteFloat
    hg_opco_entreprise: NonEmptyString
    hg_taille_entreprise: FiniteFloat


class PredictionResponse(BaseModel):
    """Business response returned by a successful model inference."""

    risk_score: float
    threshold: float
    risk_flag: bool
    model_name: str
    model_version: str
