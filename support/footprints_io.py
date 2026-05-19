from typing import Optional
import os

import pandas as pd


def save_footprints_csv(
    footprints: pd.DataFrame,
    output_path: str,
    mode: str = "write",
    key_columns: Optional[list[str]] = None,
) -> pd.DataFrame:
    if mode not in {"write", "append"}:
        raise ValueError("mode must be either 'write' or 'append'")

    if "Value" not in footprints.columns:
        raise ValueError("footprints must contain a 'Value' column")

    if key_columns is None:
        key_columns = [column for column in footprints.columns if column != "Value"]

    missing_key_columns = [column for column in key_columns if column not in footprints.columns]
    if missing_key_columns:
        raise ValueError(
            f"key columns not found in footprints: {missing_key_columns}"
        )

    footprints_to_save = footprints.copy()

    if mode == "append" and os.path.exists(output_path):
        existing = pd.read_csv(output_path)

        missing_existing_columns = [
            column for column in footprints_to_save.columns if column not in existing.columns
        ]
        if missing_existing_columns:
            raise ValueError(
                "existing CSV is missing required columns: "
                f"{missing_existing_columns}"
            )

        extra_existing_columns = [
            column for column in existing.columns if column not in footprints_to_save.columns
        ]
        if extra_existing_columns:
            footprints_to_save = footprints_to_save.reindex(
                columns=[*footprints_to_save.columns, *extra_existing_columns]
            )

        existing = existing.reindex(columns=footprints_to_save.columns)

        # Keep the new calculation for matching keys and preserve old rows for other keys.
        existing = existing.merge(
            footprints_to_save[key_columns].drop_duplicates(),
            on=key_columns,
            how="left",
            indicator=True,
        )
        existing = existing.loc[existing["_merge"] == "left_only", footprints_to_save.columns]

        footprints_to_save = pd.concat(
            [existing, footprints_to_save],
            axis=0,
            ignore_index=True,
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    footprints_to_save.to_csv(output_path, index=False)

    return footprints_to_save