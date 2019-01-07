import collections
import enum
import pulp

# A person who can appear in the rota.  People have no names, as
# 'generate_model' is given a dict 'name -> person'.
Person = collections.namedtuple('Person', ['team', 'can_do_inhours', 'num_times_inhours', 'num_times_shadow', 'can_do_oncall', 'num_times_oncall', 'forbidden_weeks'])


class Role(enum.Enum):
    """All the different types of role.
    """

    PRIMARY          = enum.auto()
    SECONDARY        = enum.auto()
    SHADOW           = enum.auto()
    PRIMARY_ONCALL   = enum.auto()
    SECONDARY_ONCALL = enum.auto()


def generate_model(num_weeks, max_shifts_per_person, people):
    """Generate the mathematical model of the rota problem.

    TODO: "including earlier instances in this rota" parts
    TODO: 2.5
    TODO: optimisations
    """

    prob = pulp.LpProblem('2ndline rota')

    # Model the rota as a [num weeks x num people x num roles] matrix, where rota[week,person,role] == that person has that role for that week.
    rota = pulp.LpVariable.dicts('rota', ((week, person, role.name) for week in range(num_weeks) for person in people.keys() for role in Role), cat='Binary')

    # In every week:
    for week in range(num_weeks):
        # [1.1] Each role must be assigned to exactly one person, except shadow which may be unassigned.
        for role in Role:
            prob += pulp.lpSum(rota[week, person, Role.PRIMARY.name]          for person in people.keys()) == 1
            prob += pulp.lpSum(rota[week, person, Role.SECONDARY.name]        for person in people.keys()) == 1
            prob += pulp.lpSum(rota[week, person, Role.SHADOW.name]           for person in people.keys()) <= 1
            prob += pulp.lpSum(rota[week, person, Role.PRIMARY_ONCALL.name]   for person in people.keys()) == 1
            prob += pulp.lpSum(rota[week, person, Role.SECONDARY_ONCALL.name] for person in people.keys()) == 1

        # [1.2.1] Primary must: be able to do in-hours support
        # [1.3.1] Secondary must: be able to do in-hours support
        # [1.4.1] Shadow must: be able to do in-hours support
        # [1.5.1] Primary oncall must: be able to do out-of-hours support
        # [1.6.1] Secondary oncall must: be able to do out-of-hours support
        for person, p in people.items():
            prob += rota[week, person, Role.PRIMARY.name]          <= (1 if p.can_do_inhours else 0)
            prob += rota[week, person, Role.SECONDARY.name]        <= (1 if p.can_do_inhours else 0)
            prob += rota[week, person, Role.SHADOW.name]           <= (1 if p.can_do_inhours else 0)
            prob += rota[week, person, Role.PRIMARY_ONCALL.name]   <= (1 if p.can_do_oncall  else 0)
            prob += rota[week, person, Role.SECONDARY_ONCALL.name] <= (1 if p.can_do_oncall  else 0)

        # [1.2.2] Primary must: have been on in-hours support at least 3 times (TODO: including earlier instances in this rota)
        # [1.3.2] Secondary must: have shadowed at least twice (TODO: including earlier instances in this rota)
        # [1.4.2] Shadow must: have shadowed at most once before (TODO: including earlier instances in this rota)
        # [1.6.2] Secondary oncall must: have done out-of-hours support at least 3 times (TODO: including earlier instances in this rota)
        for person, p in people.items():
            prob += rota[week, person, Role.PRIMARY.name]          <= (1 if p.num_times_inhours >= 3 else 0)
            prob += rota[week, person, Role.SECONDARY.name]        <= (1 if p.num_times_shadow  >= 2 else 0)
            prob += rota[week, person, Role.SHADOW.name]           <= (1 if p.num_times_shadow  <= 1 else 0)
            prob += rota[week, person, Role.SECONDARY_ONCALL.name] <= (1 if p.num_times_oncall  >= 3 else 0)

    # A person must:
    for person, p in people.items():
        # [2.1] Not be assigned more than one role in the same week
        for week in range(num_weeks):
            prob += pulp.lpSum(rota[week, person, role.name] for role in Role) <= 1

        # [2.2] Not be assigned roles in two adjacent weeks
        for week in range(num_weeks):
            if week == num_weeks - 1:
                break
            prob += pulp.lpSum(rota[week, person, role.name] for role in Role) + pulp.lpSum(rota[week + 1, person, role.name] for role in Role) <= 1

        # [2.3] Not be assigned a role in a week they cannot do
        for forbidden_week in p.forbidden_weeks:
            prob += pulp.lpSum(rota[forbidden_week, person, role.name] for role in Role) == 0

        # [2.4] Not be assigned more than `max_shifts_per_person` roles in total
        prob += pulp.lpSum(rota[week, person, role.name] for week in range(num_weeks) for role in Role) <= max_shifts_per_person

    reurn (rota, prob)