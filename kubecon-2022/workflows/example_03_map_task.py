"""Flyte Intro: Grid search Map Tasks."""

from dataclasses import dataclass
from typing import List, Tuple, NamedTuple

import pandas as pd
from sklearn.linear_model import LogisticRegression
from dataclasses_json import dataclass_json

from flytekit import task, workflow, map_task
from flytekit.types.structured import StructuredDataset

from .example_00_intro import (
    get_data,
    split_data,
    evaluate,
    FEATURES,
    TARGET,
)
from .example_04_dynamic import get_best_model


@dataclass_json
@dataclass
class TrainArgs:
    """✨ Create a data-type to encapsulate the arguments to a single training run"""

    data: StructuredDataset
    hyperparameters: dict


@task
def train_model(train_args: TrainArgs) -> LogisticRegression:
    """This is a unary task function for our model to make it mappable"""
    data: pd.DataFrame = train_args.data.open(pd.DataFrame).all()
    model = LogisticRegression(max_iter=5000, **train_args.hyperparameters)
    return model.fit(data[FEATURES], data[TARGET])


@task
def prepare_train_args(
    train_data: StructuredDataset, hyperparam_grid: List[dict]
) -> List[TrainArgs]:
    """👜 We then create a task to create a list of TrainArgs to map over."""
    return [TrainArgs(train_data, hp) for hp in hyperparam_grid]


@workflow
def tune_model(
    hyperparam_grid: List[dict],
    tune_data: StructuredDataset,
    val_size: float,
    random_state: int,
) -> Tuple[LogisticRegression, float]:
    """And finally, a workflow that performs grid search."""
    train_data, val_data = split_data(
        data=tune_data, test_size=val_size, random_state=random_state
    )
    # wrapping the `train_model` task in `map_task` allows us to parallelize
    # our grid search.
    models = map_task(train_model, concurrency=5)(
        train_args=prepare_train_args(
            train_data=train_data, hyperparam_grid=hyperparam_grid
        )
    )
    return get_best_model(models=models, val_data=val_data)


@workflow
def tuning_workflow(
    hyperparam_grid: List[dict] = [
        {"C": 1.0},
        {"C": 0.1},
        {"C": 0.01},
        {"C": 0.001},
    ],
    val_size: float = 0.2,
    test_size: float = 0.2,
    random_state: int = 42,
) -> NamedTuple(
    "TuningResults",
    best_model=LogisticRegression,
    best_val_acc=float,
    train_acc=float,
    test_acc=float,
):

    # get and split data
    data = get_data()
    tune_data, test_data = split_data(
        data=data, test_size=test_size, random_state=random_state
    )

    # tune model over hyperparameter grid
    best_model, best_val_acc = tune_model(
        hyperparam_grid=hyperparam_grid,
        tune_data=tune_data,
        val_size=val_size,
        random_state=random_state,
    )

    # evaluate the model
    train_acc = evaluate(model=best_model, data=tune_data)
    test_acc = evaluate(model=best_model, data=test_data)

    # return model with tuning results
    return best_model, best_val_acc, train_acc, test_acc


if __name__ == "__main__":
    print(f"{tuning_workflow()}")
