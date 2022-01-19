from plans.apps import PlansConfig


class SamplePlansConfig(PlansConfig):
    name = 'example.sample_plans'
    label = 'sample_plans'
    verbose_name = 'Plans (custom)'


del PlansConfig
