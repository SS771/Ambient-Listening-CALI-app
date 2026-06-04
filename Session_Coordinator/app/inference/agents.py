from langchain_ibm import WatsonxEmbeddings, WatsonxLLM
from langchain_classic.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain.tools import tool
from langchain_classic.tools.render import render_text_description_and_args
from langchain_classic.agents.output_parsers import JSONAgentOutputParser
from langchain_classic.agents.format_scratchpad import format_log_to_str
from langchain_classic.agents import AgentExecutor
from langchain_core.runnables import RunnablePassthrough
from ibm_watsonx_ai.foundation_models.utils.enums import EmbeddingTypes
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
import os
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

isVerbose = bool(os.environ.get("verbose_output", False))

class MyLogger:
    def __init__(self, *args, **kwargs):
        self.callcount = 0
    def __call__(self, *args, **kwargs):
        if isVerbose:
            print(f"{self.callcount} ::", *args, **kwargs)
            self.callcount = self.callcount + 1

log = MyLogger()

credentials = {
    "url": "https://us-south.ml.cloud.ibm.com",
    "apikey": os.getenv("watsonx_apikey", ""),
}
project_id = os.getenv("watsonx_project_id", "")


log("creds done")

class WlcPromptable():
    def prompt(self, data):
        raise NotImplementedError()

class PhysicalAssessment(BaseModel):
    summary: str = Field(description="Overall summary of patient visit")
    eyes: str = Field(description="Assessment for EYES category; list exceptional information or 'no information was noted'")
    ears_nose_mouth_throat: str = Field(description="Assessment for EARS NOSE MOUTH AND THROAT category; list exceptional information or 'no information was noted'")
    neck: str = Field(description="Assessment for NECK category; list exceptional information or 'no information was noted'")
    respiratory: str = Field(description="Assessment for RESPIRATORY category; list exceptional information or 'no information was noted'")
    cardiovascular: str = Field(description="Assessment for CARDIOVASCULAR category; list exceptional information or 'no information was noted'")
    gastrointestinal: str = Field(description="Assessment for GASTROINTESTINAL category; list exceptional information or 'no information was noted'")
    genitourinary: str = Field(description="Assessment for GENITOURINARY category; list exceptional information or 'no information was noted'")
    lymphatics: str = Field(description="Assessment for LYMPHATICS category; list exceptional information or 'no information was noted'")
    musculoskeletal_extremities: str = Field(description="Assessment for MUSCULOSKELETAL/EXTREMITIES category; list exceptional information or 'no information was noted'")
    skin: str = Field(description="Assessment for SKIN category; list exceptional information or 'no information was noted'")
    neurologic: str = Field(description="Assessment for NEUROLOGIC category; list exceptional information or 'no information was noted'")
    psychiatric: str = Field(description="Assessment for PSYCHIATRIC category; list exceptional information or 'no information was noted'")

class Vitals(BaseModel):
    summary: str = Field(description="Overall summary of patient visit")
    note: str = Field(description="Any observation notes of patient visit")
    bps: str = Field(description=" it is systolic blood pressure (SBP), which is the top number")
    bpd: str = Field(description="diastolic blood pressure (DBP), which is the bottom number")
    weight: str = Field(description="weight of patient")
    height: str = Field(description="height of patient")
    temperature: str = Field(description="temperature of patient")
    temperature_method: str = Field(description="method used to get temperature(oral , rectal , Axillary (Armpit),Tympanic (Ear),Temporal Artery (Forehead))")
    pulse: str = Field(description="pulse rate of patient")
    respiration: str = Field(description="Respiratory rate of patient")
    waist_circ: str = Field(description="waist circumference of patient")
    head_circ: str = Field(description="head circumference of patient")
    oxygen_saturation: str = Field(description="oxygen_saturation of patient")

class VitalsAgent(WlcPromptable):
    def __init__(self, *args, **kwargs):
        self.chain = self.makeAgentChain()
    def makeLLM(self):
        return WatsonxLLM(
            model_id= "meta-llama/llama-3-3-70b-instruct",
            url=credentials.get("url"),
            apikey=credentials.get("apikey"),
            project_id=project_id,
            params={
                GenParams.DECODING_METHOD: "greedy",
                GenParams.TEMPERATURE: 0.3,
                GenParams.MIN_NEW_TOKENS: 5,
                GenParams.MAX_NEW_TOKENS: 1500,
                GenParams.STOP_SEQUENCES: ["Human:", "Observation"],
            },
        )
    def makeAgentChain(self):
        llm = self.makeLLM()

        output_parser = PydanticOutputParser(pydantic_object=Vitals)
        
        #format_instruction=output_parser.get_format_instructions()
        
        template = '''You are a medical summarization expert. Analyze this patient visit {transcript} to answer following categories:
        summary, note, BPs, BPd, weight, height, temperature, temperature_method, pulse, respiration, waist_circ, head_circ, oxygen_saturation.
        Ensure each category is included in your assessment. If the category is not mentioned in the patient visit , simply leave it empty. \n
        Format your response as a JSON object matching the following schema:
        {format_instruction}'''
        
        template = PromptTemplate(
            template=template,
            input_variables=['transcript'],
            partial_variables={'format_instruction':output_parser.get_format_instructions()}
        )

        chain = template | llm | output_parser
        return chain
    def prompt(self, data)->Vitals:
        return self.chain.invoke({'transcript':data})

class PhysicalAssessmentAgent(WlcPromptable):
    def __init__(self, *args, **kwargs):
        self.chain = self.makeAgentChain()

    def makeAgentChain(self):
        llm = WatsonxLLM(
            model_id= "meta-llama/llama-3-3-70b-instruct",
            url=credentials.get("url"),
            apikey=credentials.get("apikey"),
            project_id=project_id,
            params={
                GenParams.DECODING_METHOD: "greedy",
                GenParams.TEMPERATURE: 0.3,
                GenParams.MIN_NEW_TOKENS: 5,
                GenParams.MAX_NEW_TOKENS: 1500,
                GenParams.STOP_SEQUENCES: ["Human:", "Observation"],
            },
        )

        output_parser = PydanticOutputParser(pydantic_object=PhysicalAssessment)
        format_instruction=output_parser.get_format_instructions()
        template = '''
        You are a medical summarization expert. Analyze this patient visit {transcript} to provide a concise physical assessment by listing any exceptional information discussed for the following categories:
        EYES, EARS NOSE MOUTH AND THROAT, NECK, RESPIRATORY, CARDIOVASCULAR, GASTROINTESTINAL, GENITOURINARY, LYMPHATICS, MUSCULOSKELETAL/EXTREMITIES, SKIN, NEUROLOGIC, PSYCHIATRIC.
        Ensure each category is included in your assessment. If the category is not mentioned in the patient visit , simply state 'no information was noted'. \n
        Format your response as a JSON object matching the following schema:
        {format_instruction}'''
        template = PromptTemplate(
            template=template,
            input_variables=['transcript'],
            partial_variables={'format_instruction':output_parser.get_format_instructions()}
        )
        chain = template | llm | output_parser
        return chain
    
    def prompt(self, data)->PhysicalAssessment: #returns object with datafields
        return self.chain.invoke({'transcript':data})

class AdditionalRecommendationsAgent():
    def __init__(self, *args, **kwargs):
        self.agent_executor = self.makeAgentExecutor()
    def makeAgentExecutor(self):
        llm = WatsonxLLM(
            model_id= "meta-llama/llama-3-3-70b-instruct",
            url=credentials.get("url"),
            apikey=credentials.get("apikey"),
            project_id=project_id,
            params={
                GenParams.DECODING_METHOD: "greedy",
                GenParams.TEMPERATURE: 0.3,
                GenParams.MIN_NEW_TOKENS: 5,
                GenParams.MAX_NEW_TOKENS: 1000,
                GenParams.STOP_SEQUENCES: ["Human:", "Observation"],
            },
        )

        log("llm done")

        embeddings = WatsonxEmbeddings(
            model_id="ibm/slate-125m-english-rtrvr-v2",
            url=credentials["url"],
            apikey=credentials["apikey"],
            project_id=project_id,
        )

        persist_directory = os.environ.get("agent_database_dir", 'content/chroma')
        #os.makedirs(persist_directory, exist_ok=True)

        vector_dbis = Chroma( persist_directory=persist_directory,
            collection_name="IncentiveSpiro",
            embedding_function=embeddings )

        vector_dbi = Chroma( persist_directory=persist_directory,
            collection_name="Inhaler",
            embedding_function=embeddings   )

        vector_dbc = Chroma( persist_directory=persist_directory,
            collection_name="catheter",
            embedding_function=embeddings )

        vector_dbcd = Chroma( persist_directory=persist_directory,
            collection_name="compressiondevice",
            embedding_function=embeddings  )

        vector_dbpa = Chroma(
            persist_directory=persist_directory,
            collection_name="painassessment",
            embedding_function=embeddings )

        vector_dbwpi = Chroma(  persist_directory=persist_directory ,
            collection_name="woundpressureinjury",
            embedding_function=embeddings  )

        log("db good")

        incspiro_retriever = vector_dbis.as_retriever(search_type="similarity_score_threshold",search_kwargs={"score_threshold": 0.6})
        inhaler_retriever = vector_dbi.as_retriever(search_type="similarity_score_threshold",search_kwargs={"score_threshold": 0.6})
        catheter_retriever = vector_dbc.as_retriever(search_type="similarity_score_threshold",search_kwargs={"score_threshold": 0.6})
        compresdevic_retriever = vector_dbcd.as_retriever(search_type="similarity_score_threshold",search_kwargs={"score_threshold": 0.6})
        pain_retriever = vector_dbpa.as_retriever(search_type="similarity_score_threshold",search_kwargs={"score_threshold": 0.6})
        wound_retriever = vector_dbwpi.as_retriever(search_type="similarity_score_threshold",search_kwargs={"score_threshold": 0.6})
        @tool
        def incentive_spirometer(question: str):
            """tool incentive spirometer is a medical device used for deep breathing exercises to improve lung expansion , especially after surgery or for patients with lung diseases like COPD """
            context = incspiro_retriever.invoke(question)
            return context

        @tool
        def inhaler(question: str):
            """tool inhaler medical device delivers medication directly to the lungs to treat conditions like asthma. it helps in breathing. """
            context = inhaler_retriever.invoke(question)
            return context


        @tool
        def urinary_catheter(question: str):
            """Get context about device urinary catheter medical device used related to urine issues"""
            context = catheter_retriever.invoke(question)
            return context

        @tool
        def compressiondevice(question: str):
            """tool compression devices are used to improve blood flow, prevent blood clots, and reduce swelling and pain. They are commonly used to treat conditions like deep vein thrombosis (DVT), lymphedema, and venous insufficiency, and are often used after surgery or to manage chronic venous disease. These devices work by applying timed pressure to the limbs, helping to move fluid through the veins and lymphatic vessels."""
            context = compresdevic_retriever.invoke(question)
            return context


        @tool
        def pain_assess(question: str):
            """Get context about pain related. always assess and document pain location, severity (i.e., numeric rating scale, Wong-Baker FACES scale), onset (i.e., chronic or acute), quality (i.e., sharp, dull, intermittent, throbbing, ache,
        burning, shooting, crushing, stabbing)"""
            context = pain_retriever.invoke(question)
            return context


        @tool
        def wound(question: str):
            """Get context about wound. wound is also called as pressure injury."""
            context = wound_retriever.invoke(question)
            return context

        
        tools = [incentive_spirometer,inhaler,urinary_catheter,compressiondevice,pain_assess,wound]


        log("tools setup")

        #can say "if using a tool identify the tool's name"
        system_prompt = """Respond to the human as helpfully and accurately as possible. You have access to the following tools: {tools}
        Use a json blob to specify a tool by providing an action key (tool name) and an action_input key (tool input).
        Valid "action" values: "Final Answer" or {tool_names}
        Provide only ONE action per $JSON_BLOB, as shown:"
        ```
        {{
        "action": $TOOL_NAME,
        "action_input": $INPUT
        }}
        ```
        Follow this format:
        Question: input question to answer
        Thought: consider previous and subsequent steps
        Action:
        ```
        $JSON_BLOB
        ```
        Observation: action result
        ... (repeat Thought/Action/Observation N times)
        Thought: I know what to respond
        Action:
        ```
        {{
        "action": "Final Answer",
        "action_input": "Final response to human"
        }}
        Begin! Reminder to ALWAYS respond with a valid json blob of a single action.
        Respond directly if appropriate. Format is Action:```$JSON_BLOB```then Observation"""

        human_prompt = """{input}
        {agent_scratchpad}
        (reminder to always respond in a JSON blob)"""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", human_prompt),
            ]
        )

        prompt = prompt.partial(
            tools=render_text_description_and_args(list(tools)),
            tool_names=", ".join([t.name for t in tools]),
        )


        log("prompt setup")



        chain = (
            RunnablePassthrough.assign(
                agent_scratchpad=lambda x: format_log_to_str(x["intermediate_steps"]),
            )
            | prompt
            | llm
            | JSONAgentOutputParser()
        )

        agent_executor = AgentExecutor(
            agent=chain, tools=tools, handle_parsing_errors=True, verbose=isVerbose
        )


        log("everything setup")
        return agent_executor
    def prompt(self, data)->str: #returns direct prompt result string
        log("doAPrompt start")
        desired_prompt = """You are a medical summarization expert. Analyze the following patient visit. Based on the interaction, provide helpful additional recommendations for the nurse's conduct, including feedback on required actions such as confirming the patient's name and date of birth. Do not include a summary of the interaction and do not request feedback for your response.

        Patient visit:
        """

        full_input = desired_prompt + data
        log(full_input)

        outputOfAgent = self.agent_executor.invoke({"input": full_input})

        log("agent done", outputOfAgent)
        return outputOfAgent['output']


#SERVICES

AI_ADDITIONAL_RECOMMENDATIONS = AdditionalRecommendationsAgent()
AI_PHYSICAL_ASSESSMENT = PhysicalAssessmentAgent()
AI_VITALS = VitalsAgent()

if __name__ == "__main__": #If you invoke this file directly it'll run a quick test
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("textfile", help = "path to text file to read for output tests")
    progArgs = parser.parse_args()
    log("MAIN")
    data = None
    with open(progArgs.textfile) as f:
        data = f.read()
    print("--- PHYSICAL ASSESSMENT ---\n", AI_PHYSICAL_ASSESSMENT.prompt(data))
    print("--- ADDITIONAL RECOMMENDATIONS ---\n", AI_ADDITIONAL_RECOMMENDATIONS.prompt(data))
    print("--- VITALS ---\n", AI_VITALS.prompt(data))