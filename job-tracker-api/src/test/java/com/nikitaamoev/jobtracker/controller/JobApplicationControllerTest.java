package com.nikitaamoev.jobtracker.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** Интеграционный тест: поднимает приложение с H2 и проверяет API целиком. */
@SpringBootTest
@AutoConfigureMockMvc
class JobApplicationControllerTest {

    @Autowired
    private MockMvc mvc;

    @Test
    void createAndGetApplication() throws Exception {
        mvc.perform(post("/api/applications")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"company":"Acme","position":"AI Automation Engineer","salaryUsd":1000}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").isNumber())
                .andExpect(jsonPath("$.status").value("FOUND"));

        mvc.perform(get("/api/applications").param("company", "acm"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].company").value("Acme"));
    }

    @Test
    void rejectsInvalidRequest() throws Exception {
        mvc.perform(post("/api/applications")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"company\":\"\",\"position\":\"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors.company").exists());
    }

    @Test
    void returns404ForMissing() throws Exception {
        mvc.perform(get("/api/applications/9999"))
                .andExpect(status().isNotFound());
    }
}
