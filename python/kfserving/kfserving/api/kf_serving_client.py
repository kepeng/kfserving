# Copyright 2019 The Kubeflow Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
from kubernetes import client, config

from ..constants import constants
from ..utils import utils
from .creds_utils import set_gcs_credentials, set_s3_credentials, set_azure_credentials
from .kf_serving_watch import watch as isvc_watch
from ..models.v1alpha2_inference_service import V1alpha2InferenceService
from ..models.v1alpha2_inference_service_spec import V1alpha2InferenceServiceSpec


class KFServingClient(object):

    def __init__(self, config_file=None, context=None, # pylint: disable=too-many-arguments
                 client_configuration=None, persist_config=True):
        """
        KFServing client constructor
        :param config_file: kubeconfig file, defaults to ~/.kube/config
        :param context: kubernetes context
        :param client_configuration: kubernetes configuration object
        :param persist_config:
        """
        if config_file or not utils.is_running_in_k8s():
            config.load_kube_config(
                config_file=config_file,
                context=context,
                client_configuration=client_configuration,
                persist_config=persist_config)
        else:
            config.load_incluster_config()
        self.core_api = client.CoreV1Api()
        self.app_api = client.AppsV1Api()
        self.api_instance = client.CustomObjectsApi()

    def set_credentials(self, storage_type, namespace=None, credentials_file=None,
                        service_account=constants.DEFAULT_SA_NAME, **kwargs):
        """
        Setup credentials for KFServing.

        :param storage_type: Valid value: GCS or S3 (required)
        :param namespace: inference service deployment namespace
        :param credentials_file: the path for the credentials file.
        :param service_account: the name of service account.
        :param kwargs: Others parameters for each storage_type
        :return:
        """

        if namespace is None:
            namespace = utils.get_default_target_namespace()

        if storage_type.lower() == 'gcs':
            if credentials_file is None:
                credentials_file = constants.GCS_DEFAULT_CREDS_FILE
            set_gcs_credentials(namespace=namespace,
                                credentials_file=credentials_file,
                                service_account=service_account)
        elif storage_type.lower() == 's3':
            if credentials_file is None:
                credentials_file = constants.S3_DEFAULT_CREDS_FILE
            set_s3_credentials(namespace=namespace,
                               credentials_file=credentials_file,
                               service_account=service_account,
                               **kwargs)
        elif storage_type.lower() == 'azure':
            if credentials_file is None:
                credentials_file = constants.AZ_DEFAULT_CREDS_FILE
            set_azure_credentials(namespace=namespace,
                                  credentials_file=credentials_file,
                                  service_account=service_account)
        else:
            raise RuntimeError("Invalid storage_type: %s, only support GCS, S3 and Azure\
                currently.\n" % storage_type)

    def create(self, inferenceservice, namespace=None, watch=False, timeout_seconds=600, version=constants.KFSERVING_VERSION): #pylint:disable=inconsistent-return-statements
        """
        Create the inference service
        :param inferenceservice: inference service object
        :param namespace: defaults to current or default namespace
        :param watch: True to watch the created service until timeout elapsed or status is ready
        :param timeout_seconds: timeout seconds for watch, default to 600s
        :param version: api group version
        :return: created inference service
        """

        if namespace is None:
            namespace = utils.set_isvc_namespace(inferenceservice)

        try:
            outputs = self.api_instance.create_namespaced_custom_object(
                constants.KFSERVING_GROUP,
                version,
                namespace,
                constants.KFSERVING_PLURAL,
                inferenceservice)
        except client.rest.ApiException as e:
            raise RuntimeError(
                "Exception when calling CustomObjectsApi->create_namespaced_custom_object:\
                 %s\n" % e)

        if watch:
            isvc_watch(
                name=outputs['metadata']['name'],
                namespace=namespace,
                timeout_seconds=timeout_seconds)
        else:
            return outputs

    def get(self, name=None, namespace=None, watch=False, timeout_seconds=600, version=constants.KFSERVING_VERSION): #pylint:disable=inconsistent-return-statements
        """
        Get the inference service
        :param name: existing inference service name
        :param namespace: defaults to current or default namespace
        :param watch: True to watch the service until timeout elapsed or status is ready
        :param timeout_seconds: timeout seconds for watch, default to 600s
        :param version: api group version
        :return: inference service
        """
        if namespace is None:
            namespace = utils.get_default_target_namespace()

        if name:
            if watch:
                isvc_watch(
                    name=name,
                    namespace=namespace,
                    timeout_seconds=timeout_seconds)
            else:
                try:
                    return self.api_instance.get_namespaced_custom_object(
                        constants.KFSERVING_GROUP,
                        version,
                        namespace,
                        constants.KFSERVING_PLURAL,
                        name)
                except client.rest.ApiException as e:
                    raise RuntimeError(
                        "Exception when calling CustomObjectsApi->get_namespaced_custom_object:\
                        %s\n" % e)
        else:
            if watch:
                isvc_watch(
                    namespace=namespace,
                    timeout_seconds=timeout_seconds)
            else:
                try:
                    return self.api_instance.list_namespaced_custom_object(
                        constants.KFSERVING_GROUP,
                        version,
                        namespace,
                        constants.KFSERVING_PLURAL)
                except client.rest.ApiException as e:
                    raise RuntimeError(
                        "Exception when calling CustomObjectsApi->list_namespaced_custom_object:\
                        %s\n" % e)

    def patch(self, name, inferenceservice, namespace=None, watch=False, timeout_seconds=600, version=constants.KFSERVING_VERSION): # pylint:disable=too-many-arguments,inconsistent-return-statements
        """
        Patch existing inference service
        :param name: existing inference service name
        :param inferenceservice: patched inference service
        :param namespace: defaults to current or default namespace
        :param watch: True to watch the patched service until timeout elapsed or status is ready
        :param timeout_seconds: timeout seconds for watch, default to 600s
        :param version: api group version
        :return: patched inference service
        """
        if namespace is None:
            namespace = utils.set_isvc_namespace(inferenceservice)

        try:
            outputs = self.api_instance.patch_namespaced_custom_object(
                constants.KFSERVING_GROUP,
                version,
                namespace,
                constants.KFSERVING_PLURAL,
                name,
                inferenceservice)
        except client.rest.ApiException as e:
            raise RuntimeError(
                "Exception when calling CustomObjectsApi->patch_namespaced_custom_object:\
                 %s\n" % e)

        if watch:
            # Sleep 3 to avoid status still be True within a very short time.
            time.sleep(3)
            isvc_watch(
                name=outputs['metadata']['name'],
                namespace=namespace,
                timeout_seconds=timeout_seconds)
        else:
            return outputs

    def replace(self, name, inferenceservice, namespace=None, watch=False, timeout_seconds=600, version=constants.KFSERVING_VERSION): # pylint:disable=too-many-arguments,inconsistent-return-statements
        """
        Replace the existing inference service
        :param name: existing inference service name
        :param inferenceservice: replacing inference service
        :param namespace: defaults to current or default namespace
        :param watch: True to watch the replaced service until timeout elapsed or status is ready
        :param timeout_seconds: timeout seconds for watch, default to 600s
        :param version: api group version
        :return: replaced inference service
        """

        if namespace is None:
            namespace = utils.set_isvc_namespace(inferenceservice)

        if inferenceservice.metadata.resource_version is None:
            current_isvc = self.get(name, namespace=namespace)
            current_resource_version = current_isvc['metadata']['resourceVersion']
            inferenceservice.metadata.resource_version = current_resource_version

        try:
            outputs = self.api_instance.replace_namespaced_custom_object(
                constants.KFSERVING_GROUP,
                version,
                namespace,
                constants.KFSERVING_PLURAL,
                name,
                inferenceservice)
        except client.rest.ApiException as e:
            raise RuntimeError(
                "Exception when calling CustomObjectsApi->replace_namespaced_custom_object:\
                 %s\n" % e)

        if watch:
            isvc_watch(
                name=outputs['metadata']['name'],
                namespace=namespace,
                timeout_seconds=timeout_seconds)
        else:
            return outputs

    def rollout_canary(self, name, percent, namespace=None, # pylint:disable=too-many-arguments,inconsistent-return-statements
                       canary=None, watch=False, timeout_seconds=600, version=constants.KFSERVING_VERSION):
        """
        Rollout the canary endpoint
        :param name: inference service name
        :param percent: traffic percentage to the canary endpoint
        :param namespace: defaults to current or default namespace
        :param canary: canary endpoint spec
        :param watch: True to watch the service until timeout elapsed or status is ready
        :param timeout_seconds: timeout seconds for watch, default to 600s
        :param version: api group version
        :return: inference service with canary endpoint
        """

        if namespace is None:
            namespace = utils.get_default_target_namespace()

        current_isvc = self.get(name, namespace=namespace)

        if canary is None and 'canary' not in current_isvc['spec']:
            raise RuntimeError("Canary spec missing? Specify canary for the InferenceService.")

        current_isvc['spec']['canaryTrafficPercent'] = percent
        if canary:
            current_isvc['spec']['default'] = canary
            current_isvc['spec']['canary'] = canary

        return self.patch(name=name, inferenceservice=current_isvc, namespace=namespace,
                          watch=watch, timeout_seconds=timeout_seconds, version=version)

    def delete(self, name, namespace=None, version=constants.KFSERVING_VERSION):
        """
        Delete the inference service
        :param name: inference service name
        :param namespace: defaults to current or default namespace
        :param version: api group version
        :return:
        """
        if namespace is None:
            namespace = utils.get_default_target_namespace()

        try:
            return self.api_instance.delete_namespaced_custom_object(
                constants.KFSERVING_GROUP,
                version,
                namespace,
                constants.KFSERVING_PLURAL,
                name,
                client.V1DeleteOptions())
        except client.rest.ApiException as e:
            raise RuntimeError(
                "Exception when calling CustomObjectsApi->delete_namespaced_custom_object:\
                 %s\n" % e)


    def is_isvc_ready(self, name, namespace=None): #pylint:disable=inconsistent-return-statements
        """
        Check if the inference service is ready.
        :param name: inference service name
        :param namespace: defaults to current or default namespace
        :return:
        """
        kfsvc_status = self.get(name, namespace=namespace, version=constants.KFSERVING_V1BETA1_VERSION)
        status = 'Unknown'
        for condition in kfsvc_status['status'].get('conditions', {}):
            if condition.get('type', '') == 'Ready':
                status = condition.get('status', 'Unknown')
                return status.lower() == "true"
        return False


    def wait_isvc_ready(self, name, namespace=None, #pylint:disable=too-many-arguments
                        watch=False,
                        timeout_seconds=600,
                        polling_interval=10):
        """
        Waiting for inference service ready, print out the inference service if timeout.
        :param name: inference service name
        :param namespace: defaults to current or default namespace
        :param watch: True to watch the service until timeout elapsed or status is ready
        :param timeout_seconds: timeout seconds for waiting, default to 600s.
               Print out the InferenceService if timeout.
        :param polling_interval: The time interval to poll status
        :return:
        """
        if watch:
            isvc_watch(
                name=name,
                namespace=namespace,
                timeout_seconds=timeout_seconds)
        else:
            for _ in range(round(timeout_seconds/polling_interval)):
                time.sleep(polling_interval)
                if self.is_isvc_ready(name, namespace=namespace):
                    return

            current_isvc = self.get(name, namespace=namespace, version=constants.KFSERVING_V1BETA1_VERSION)
            raise RuntimeError("Timeout to start the InferenceService {}. \
                               The InferenceService is as following: {}".format(name, current_isvc))
