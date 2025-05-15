import wandb

wandb.init(
            name="test",
            project="test prj",
            config={"lol": 1},
            mode="online",
        )
