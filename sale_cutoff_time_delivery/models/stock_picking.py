# Copyright 2020 Camptocamp SA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    cutoff_time_hms = fields.Char(compute="_compute_cutoff_time_HMS", store=True)
    cutoff_time_diff = fields.Integer(
        compute="_compute_cutoff_time_diff",
        search="_search_cutoff_time_diff",
        store=False,
    )

    @api.depends("location_id")
    def _compute_cutoff_time_diff(self):
        for record in self:
            warehouse = record.location_id.get_warehouse()
            hour, minute = warehouse._get_hour_min_from_value(warehouse.cutoff_time)
            today_cutoff = fields.Datetime.now().replace(
                hour=hour, minute=minute, second=0
            )
            yesterday_cutoff = today_cutoff + relativedelta(days=-1)
            if record.scheduled_date < yesterday_cutoff:
                record.cutoff_time_diff = -1
            elif record.scheduled_date > today_cutoff:
                record.cutoff_time_diff = 1
            else:
                record.cutoff_time_diff = 0

    def _search_cutoff_time_diff(self, operator, value):
        if operator not in ("=", "!="):
            raise UserError(_("Unsupported search operator %s") % (operator,))
        today = fields.Datetime.now()
        yesterday = today - relativedelta(days=1)
        if value == -1:
            where = """
                to_char(scheduled_date, 'YYYY-MM-DD HH:MM') < %(yesterday)s || coalesce(cutoff_time_hms, '00:00:00')
        """
        elif value == 0:
            where = """
                to_char(scheduled_date, 'YYYY-MM-DD HH:MM') >= %(yesterday)s || coalesce(cutoff_time_hms, '00:00:00') AND
                to_char(scheduled_date, 'YYYY-MM-DD HH:MM') <= %(today)s || coalesce(cutoff_time_hms, '00:00:00')
            """
        elif value == 1:
            where = """
                to_char(scheduled_date, 'YYYY-MM-DD HH:MM') > %(today)s || coalesce(cutoff_time_hms, '00:00:00')
        """
        query = (
            "SELECT id FROM stock_picking WHERE state NOT IN ('cancel', 'done') AND "
            + where
        )

        params = {
            "yesterday": yesterday.strftime("%Y-%m-%d "),
            "today": today.strftime("%Y-%m-%d "),
        }

        self.env.cr.execute(query, params)
        rows = self.env.cr.fetchall()
        picking_ids = [row[0] for row in rows]
        if operator == "=":
            new_operator = "in"
        else:
            new_operator = "not in"
        return [("id", new_operator, picking_ids)]

    @api.depends("location_id")
    def _compute_cutoff_time_HMS(self):
        for record in self:
            warehouse = record.location_id.get_warehouse()
            hour_minute = warehouse.float_to_time_repr(warehouse.cutoff_time)
            record.cutoff_time_hms = hour_minute + ":00"
