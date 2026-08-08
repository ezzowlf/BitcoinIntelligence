from __future__ import annotations
import pandas as pd


def splits(index: pd.DatetimeIndex, train_days: int = 730, test_days: int = 365, step_days: int = 365):
    start, end = index.min(), index.max()
    cursor = start
    while cursor + pd.Timedelta(days=train_days + test_days) <= end:
        train_end = cursor + pd.Timedelta(days=train_days)
        test_end = train_end + pd.Timedelta(days=test_days)
        yield {"train": (cursor, train_end), "test": (train_end, test_end)}
        cursor += pd.Timedelta(days=step_days)


def run_walk_forward(frame: pd.DataFrame, evaluator, **split_kwargs) -> list[dict]:
    output = []
    for number, split in enumerate(splits(frame.index, **split_kwargs), 1):
        train = frame.loc[split["train"][0]:split["train"][1]]
        test = frame.loc[split["test"][0]:split["test"][1]]
        output.append({"fold": number, "in_sample": evaluator(train), "out_of_sample": evaluator(test), "train_period": split["train"], "test_period": split["test"]})
    return output

