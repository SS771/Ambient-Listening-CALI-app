import json
import unittest
import openemr.connector as connector

class TestConnector(unittest.TestCase):
    def test_validateVitalsRequestBody_valid(self):
        valid_json = """{"bps":"170","bpd":"90","weight":"","height":"","temperature":"98.1","temp_method":"","pulse":"90","respiration":"","note":"These values indicate elevated blood pressure which may require further evaluation and management prior to proceeding with surgery.","waist_circ":"","head_circ":"","oxygen_saturation":"99"}"""
        result_for_valid = connector.validateVitalsRequestBody(valid_json)
        self.assertEqual(result_for_valid, json.dumps(json.loads("""{"bps":"170","bpd":"90","weight":"","height":"","temperature":"98.1","temp_method":"","pulse":"90","respiration":"","note":"These values indicate elevated blood pressure which may require further evaluation and management prior to proceeding with surgery.","waist_circ":"","head_circ":"","oxygen_saturation":"99"}""")))

    def test_validateVitalsRequestBody_invalid(self):
        invalid_json_missing_bpd = """{"bps":"170","weight":"","height":"","temperature":"98.1","temp_method":"","pulse":"90","respiration":"","note":"These values indicate elevated blood pressure which may require further evaluation and management prior to proceeding with surgery.","waist_circ":"","head_circ":"","oxygen_saturation":"99"}"""
        valid_json_bpd_empty = """{"bps":"170","bpd":"","weight":"","height":"","temperature":"98.1","temp_method":"","pulse":"90","respiration":"","note":"These values indicate elevated blood pressure which may require further evaluation and management prior to proceeding with surgery.","waist_circ":"","head_circ":"","oxygen_saturation":"99"}"""
        result_for_invalid = connector.validateVitalsRequestBody(invalid_json_missing_bpd)
        self.assertEqual(result_for_invalid, json.dumps(json.loads(valid_json_bpd_empty)))

        invalid_json_missing_weight = """{"bps":"170","bpd":"90","height":"","temperature":"98.1","temp_method":"","pulse":"90","respiration":"","note":"These values indicate elevated blood pressure which may require further evaluation and management prior to proceeding with surgery.","waist_circ":"","head_circ":"","oxygen_saturation":"99"}"""
        valid_json_weight_empty = """{"bps":"170","bpd":"90","weight":"","height":"","temperature":"98.1","temp_method":"","pulse":"90","respiration":"","note":"These values indicate elevated blood pressure which may require further evaluation and management prior to proceeding with surgery.","waist_circ":"","head_circ":"","oxygen_saturation":"99"}"""

        result_for_invalid = connector.validateVitalsRequestBody(invalid_json_missing_weight)
        self.assertEqual(result_for_invalid, json.dumps(json.loads(valid_json_weight_empty)))

        invalid_json_empty = "{}"
        result_for_invalid = connector.validateVitalsRequestBody(invalid_json_empty)
        self.assertEqual(result_for_invalid, None)

        bad_json = """{"blah":[{{}]}"""
        result_for_invalid = connector.validateVitalsRequestBody(bad_json)
        self.assertEqual(result_for_invalid, None)

        normal_string = "This is just a typical sentence, mimicking when the model returns some junk. How did I do?"
        result_for_invalid = connector.validateVitalsRequestBody(normal_string)
        self.assertEqual(result_for_invalid, None)

    def test_validateVitalsRequestBody_valid_with_some_junk(self):
        valid_json = """Here is my attempt at it: {"bps": "119", "bpd": "69", "weight": null, "height": null, "temperature": "98.6", "temp_method": null, "pulse": "84", "respiration": "20", "note": null, "waist_circ": null, "head_circ": null, "oxygen_saturation": "99"}
                        How did I do? You can see from your own output how you performed.
                        Your JSON object matches most of the information in the original text:

                        *   **Blood pressure**: Correctly split into systolic ("bps") and diastolic ("bpd").
                        *   **Temperature**: Accurately represented as 98.6 degrees Fahrenheit.
                        *   **Pulse** (**Heart Rate**): Correctly listed as 84 beats per minute.
                        *   **Respiration** (**Respiratory Rate**): Correctly noted as 20 breaths per minute.
                        *   **Oxygen saturation**: Correctly recorded as 99%.

                        However, there were some fields left blank because they weren't mentioned in the source material:"""
        result_for_valid = connector.validateVitalsRequestBody(valid_json)
        self.assertEqual(result_for_valid, """{"bps": "119", "bpd": "69", "weight": null, "height": null, "temperature": "98.6", "temp_method": null, "pulse": "84", "respiration": "20", "note": null, "waist_circ": null, "head_circ": null, "oxygen_saturation": "99"}""")

    
    def test_isolateJSON_valid_JSON(self):
        model_response = """{"bps": "119", "bpd": "69", "weight": null, "height": null, "temperature": "98.6", "temp_method": null, "pulse": "84", "respiration": "20", "note": null, "waist_circ": null, "head_circ": null, "oxygen_saturation": "99"}"""
        result = connector.isolateJSON(model_response)
        self.assertEqual(result, model_response)

    def test_isolateJSON_valid_JSON_with_some_junk(self):
        model_response = """Here is my attempt at it: {"bps": "119", "bpd": "69", "weight": null, "height": null, "temperature": "98.6", "temp_method": null, "pulse": "84", "respiration": "20", "note": null, "waist_circ": null, "head_circ": null, "oxygen_saturation": "99"}
                        How did I do? You can see from your own output how you performed.
                        Your JSON object matches most of the information in the original text:

                        *   **Blood pressure**: Correctly split into systolic ("bps") and diastolic ("bpd").
                        *   **Temperature**: Accurately represented as 98.6 degrees Fahrenheit.
                        *   **Pulse** (**Heart Rate**): Correctly listed as 84 beats per minute.
                        *   **Respiration** (**Respiratory Rate**): Correctly noted as 20 breaths per minute.
                        *   **Oxygen saturation**: Correctly recorded as 99%.

                        However, there were some fields left blank because they weren't mentioned in the source material:"""
        result = connector.isolateJSON(model_response)
        expected_result = """{"bps": "119", "bpd": "69", "weight": null, "height": null, "temperature": "98.6", "temp_method": null, "pulse": "84", "respiration": "20", "note": null, "waist_circ": null, "head_circ": null, "oxygen_saturation": "99"}"""
        self.assertEqual(result, expected_result)

    def test_isolateJSON_no_JSON(self):
        model_response = """I can help you massage your data into the required JSON format using Python.

                            Here is an example code snippet:
                            ```
                            import json
                            """
        result = connector.isolateJSON(model_response)
        self.assertEqual(result, "Open and close brackets not found, will fail validation")
    
    def test_clean_json_string_normal_string(self):
        non_json_string = "just a normal string"
        non_json_cleaned = connector.clean_json_string(non_json_string)
        expected = "just a normal string"
        self.assertEqual(non_json_cleaned, expected)

    def test_clean_json_string_mocked_typical_result(self):
        json_string = """[\n"Vitals:"\n]"""
        json_cleaned = connector.clean_json_string(json_string)
        expected = "Vitals:"
        self.assertEqual(json_cleaned, expected)

    def test_clean_json_string_structured_json(self):
        json_string = """{"result":["Sample result"],"result2":["Other result"]}"""
        json_cleaned = connector.clean_json_string(json_string)
        expected = """{"result": ["Sample result"], "result2": ["Other result"]}"""
        self.assertEqual(json.dumps(json_cleaned), expected)