"""initial relational schema

Revision ID: 1f2e3d4c5b6a
Revises:
Create Date: 2026-03-06 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f2e3d4c5b6a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'matches',
        sa.Column('match_id', sa.String(), nullable=False),
        sa.Column('game_datetime', sa.BigInteger(), nullable=False),
        sa.Column('game_length', sa.Float(), nullable=True),
        sa.Column('game_version', sa.String(), nullable=True),
        sa.Column('tft_set_number', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('match_id'),
    )

    op.create_table(
        'users',
        sa.Column('puuid', sa.String(), nullable=False),
        sa.Column('game_name', sa.String(), nullable=False),
        sa.Column('tag_line', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('puuid'),
    )

    op.create_table(
        'traits',
        sa.Column('trait_id', sa.String(), nullable=False),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('trait_id'),
    )

    op.create_table(
        'units',
        sa.Column('unit_id', sa.String(), nullable=False),
        sa.Column('rarity', sa.Integer(), nullable=True),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('unit_id'),
    )

    op.create_table(
        'items',
        sa.Column('item_id', sa.String(), nullable=False),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('item_id'),
    )

    op.create_table(
        'user_match_stats',
        sa.Column('match_id', sa.String(), nullable=False),
        sa.Column('puuid', sa.String(), nullable=False),
        sa.Column('placement', sa.Integer(), nullable=True),
        sa.Column('damage_to_players', sa.Integer(), nullable=True),
        sa.Column('gold_left', sa.Integer(), nullable=True),
        sa.Column('last_round', sa.Integer(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=True),
        sa.Column('players_eliminated', sa.Integer(), nullable=True),
        sa.Column('time_eliminated', sa.Float(), nullable=True),
        sa.Column('win', sa.Boolean(), nullable=True),
        sa.Column('augments', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['match_id'], ['matches.match_id']),
        sa.ForeignKeyConstraint(['puuid'], ['users.puuid']),
        sa.PrimaryKeyConstraint('match_id', 'puuid'),
    )

    op.create_table(
        'trait_stats',
        sa.Column('match_id', sa.String(), nullable=False),
        sa.Column('puuid', sa.String(), nullable=False),
        sa.Column('trait_id', sa.String(), nullable=False),
        sa.Column('num_units', sa.Integer(), nullable=True),
        sa.Column('style', sa.Integer(), nullable=True),
        sa.Column('tier_current', sa.Integer(), nullable=True),
        sa.Column('tier_total', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['match_id', 'puuid'], ['user_match_stats.match_id', 'user_match_stats.puuid']),
        sa.ForeignKeyConstraint(['trait_id'], ['traits.trait_id']),
        sa.PrimaryKeyConstraint('match_id', 'puuid', 'trait_id'),
    )

    op.create_table(
        'unit_stats',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('match_id', sa.String(), nullable=False),
        sa.Column('puuid', sa.String(), nullable=False),
        sa.Column('unit_id', sa.String(), nullable=False),
        sa.Column('unit_tier', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['match_id', 'puuid'], ['user_match_stats.match_id', 'user_match_stats.puuid']),
        sa.ForeignKeyConstraint(['unit_id'], ['units.unit_id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'unit_stats_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('unit_stats_id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['unit_stats_id'], ['unit_stats.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.item_id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('unit_stats_items')
    op.drop_table('unit_stats')
    op.drop_table('trait_stats')
    op.drop_table('user_match_stats')
    op.drop_table('items')
    op.drop_table('units')
    op.drop_table('traits')
    op.drop_table('users')
    op.drop_table('matches')