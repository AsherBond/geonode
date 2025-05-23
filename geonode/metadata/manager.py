#########################################################################
#
# Copyright (C) 2024 OSGeo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import logging
import copy

from django.utils.translation import gettext as _

from geonode.metadata.handlers.abstract import MetadataHandler
from geonode.metadata.exceptions import UnsetFieldException
from geonode.metadata.i18n import I18nCache
from geonode.metadata.settings import MODEL_SCHEMA

logger = logging.getLogger(__name__)


class MetadataManager:
    """
    The metadata manager is the bridge between the API and the geonode model.
    The metadata manager will loop over all of the registered metadata handlers,
    calling their update_schema(jsonschema) which will add the subschemas of the
    fields handled by each handler. At the end of the loop, the schema will be ready
    to be delivered to the caller.
    """

    def __init__(self):
        self.root_schema = MODEL_SCHEMA
        self.handlers = {}
        self._i18n_cache = I18nCache()

    def add_handler(self, handler_id, handler):
        self.handlers[handler_id] = handler()

    def _init_schema_context(self, lang):
        return {"labels": self._i18n_cache.get_labels(lang)}

    def build_schema(self, lang=None):
        logger.debug(f"build_schema {lang}")

        schema = copy.deepcopy(self.root_schema)
        schema["title"] = _(schema["title"])

        context = self._init_schema_context(lang)

        for key, handler in self.handlers.items():
            # logger.debug(f"build_schema: update schema -> {key}")
            schema = handler.update_schema(schema, context, lang)

        # Set required fields.
        required = []
        for fieldname, field in schema["properties"].items():
            if field.get("geonode:required", False):
                required.append(fieldname)

        if required:
            schema["required"] = required
        return schema

    def get_schema(self, lang=None):
        lang = str(lang)
        thesaurus_date, schema = self._i18n_cache.get_entry(lang, I18nCache.DATA_KEY_SCHEMA)
        if schema is None:
            logger.info(f"Building schema for {lang}")
            schema = self.build_schema(lang)
            logger.debug("Schema built")
            self._i18n_cache.set(lang, I18nCache.DATA_KEY_SCHEMA, schema, thesaurus_date)
        return schema

    def build_schema_instance(self, resource, lang=None):
        schema = self.get_schema(lang)

        context = self._init_schema_context(lang)

        for handler in self.handlers.values():
            handler.load_serialization_context(resource, schema, context)

        instance = {}
        errors = {}
        for fieldname, subschema in schema["properties"].items():
            # logger.debug(f"build_schema_instance: getting handler for property {fieldname}")
            handler_id = subschema.get("geonode:handler", None)
            if not handler_id:
                logger.warning(f"Missing geonode:handler for schema property {fieldname}. Skipping")
                continue
            handler = self.handlers[handler_id]
            try:
                content = handler.get_jsonschema_instance(resource, fieldname, context, errors, lang)
                instance[fieldname] = content
            except UnsetFieldException:
                pass

        # TESTING ONLY
        if "error" in resource.title.lower():
            for fieldname in schema["properties"]:
                MetadataHandler._set_error(
                    errors, [fieldname], f"TEST: test msg for field '{fieldname}' in GET request"
                )
            instance["extraErrors"] = errors

        return instance

    def update_schema_instance(self, resource, request_obj, lang=None) -> dict:

        # Definition of the json instance
        json_instance = request_obj.data

        logger.debug(f"RECEIVED INSTANCE {json_instance}")
        resource = resource.get_real_instance()
        schema = self.get_schema()
        context = self._init_schema_context(lang)

        # We pass the request.user to the context, since it is used by the GroupHandler
        context["user"] = request_obj.user

        for handler in self.handlers.values():
            handler.load_deserialization_context(resource, schema, context)

        errors = {}

        for fieldname, subschema in schema["properties"].items():
            handler = self.handlers[subschema["geonode:handler"]]
            try:
                handler.update_resource(resource, fieldname, json_instance, context, errors)
            except Exception as e:
                MetadataHandler._set_error(
                    errors,
                    [],
                    MetadataHandler.localize_message(
                        context,
                        "metadata_error_update",
                        {"fieldname": fieldname, "handler": handler.__class__.__name__, "exc": e},
                    ),
                )
        for handler in self.handlers.values():
            try:
                handler.pre_save(resource, json_instance, context, errors)
            except Exception as e:
                logger.error(f"Error in pre_save: handler {handler.__class__.__name__}", exc_info=e)
                MetadataHandler._set_error(
                    errors,
                    [],
                    MetadataHandler.localize_message(
                        context, "metadata_error_pre_save", {"handler": handler.__class__.__name__, "exc": e}
                    ),
                )
        try:
            resource.save()
        except Exception as e:
            logger.warning(f"Error while updating schema instance: {e}")
            MetadataHandler._set_error(
                errors, [], MetadataHandler.localize_message(context, "metadata_error_save", {"exc": e})
            )

        for handler in self.handlers.values():
            try:
                handler.post_save(resource, json_instance, context, errors)
            except Exception as e:
                logger.error(f"Error in post_save: handler {handler.__class__.__name__}", exc_info=e)
                MetadataHandler._set_error(
                    errors,
                    [],
                    MetadataHandler.localize_message(
                        context, "metadata_error_post_save", {"handler": handler.__class__.__name__, "exc": e}
                    ),
                )
        # TESTING ONLY
        if "_error_" in resource.title.lower():
            _create_test_errors(schema, errors, [], "TEST: field <{schema_type}>'{path}' PUT request")

        return errors


def _create_test_errors(schema, errors, path, msg_template, create_message=True):
    if create_message:
        stringpath = "/".join(path) if path else "ROOT"
        MetadataHandler._set_error(errors, path, msg_template.format(path=stringpath, schema_type=schema["type"]))

    if schema["type"] == "object":
        for field, subschema in schema["properties"].items():
            _create_test_errors(subschema, errors, path + [field], msg_template)
    elif schema["type"] == "array":
        _create_test_errors(schema["items"], errors, path, msg_template, create_message=False)


metadata_manager = MetadataManager()
