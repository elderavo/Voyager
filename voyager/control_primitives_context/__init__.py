import os
import voyager.utils as U


def load_control_primitives_context(primitive_names=None):
    from voyager.config import config
    primitives_dir = config.CONTROL_PRIMITIVES_PATH
    if primitive_names is None:
        primitive_names = [
            primitive[:-3]
            for primitive in os.listdir(primitives_dir)
            if primitive.endswith(".js")
        ]
    primitives = [
        U.load_text(os.path.join(primitives_dir, f"{primitive_name}.js"))
        for primitive_name in primitive_names
    ]
    return primitives
